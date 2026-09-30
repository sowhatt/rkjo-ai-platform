from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from rkjo_kernel.memory import MemoryItem, MemoryQuery, MemoryScope, MemoryType
from rkjo_kernel.memory.postgres import PostgresMemoryStore


class FakeCursor:
    def __init__(self, database):
        self.database = database
        self.rows = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split()).upper()
        self.rows = []
        if normalized.startswith("CREATE"):
            return
        if normalized.startswith("INSERT"):
            memory_id, tenant_id = params[0], params[1]
            existing = self.database.get(memory_id)
            if existing is not None and existing[1] != tenant_id:
                return
            self.database[memory_id] = (
                memory_id, tenant_id, params[2], params[3], params[4],
                params[5], params[6], params[7], params[8], params[9],
                params[10], json.loads(params[11]), params[12],
            )
            self.rows = [(tenant_id,)]
            return
        if normalized.startswith("SELECT") and "MEMORY_ID = %S AND TENANT_ID = %S" in normalized:
            row = self.database.get(params[0])
            if row is not None and row[1] == params[1]:
                self.rows = [row]
            return
        if normalized.startswith("DELETE"):
            row = self.database.get(params[0])
            if row is not None and row[1] == params[1]:
                del self.database[params[0]]
                self.rows = [(params[0],)]
            return
        if normalized.startswith("SELECT"):
            rows = list(self.database.values())
            tenant_id = params[0]
            rows = [row for row in rows if row[1] == tenant_id]
            # These tests intentionally exercise the tenant-first persistence
            # contract; detailed filter SQL is asserted separately below.
            rows.sort(key=lambda row: (row[10], row[12], row[0]), reverse=True)
            self.rows = rows[: params[-1]]
            return
        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, database, counters):
        self.database = database
        self.counters = counters

    def cursor(self):
        return FakeCursor(self.database)

    def commit(self):
        self.counters["commits"] += 1

    def rollback(self):
        self.counters["rollbacks"] += 1

    def close(self):
        self.counters["closes"] += 1


def factory(database, counters):
    return lambda: FakeConnection(database, counters)


def item(*, tenant_id="tenant-a", memory_id="mem-1", content="Persistent fact"):
    return MemoryItem(
        memory_id=memory_id,
        tenant_id=tenant_id,
        scope=MemoryScope.MISSION,
        memory_type=MemoryType.FACT,
        mission_id="mission-1",
        content=content,
        importance=0.9,
        metadata={"source": "test"},
        created_at=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
    )


def test_persists_across_store_recreation():
    database, counters = {}, {"commits": 0, "rollbacks": 0, "closes": 0}
    first = PostgresMemoryStore(factory(database, counters))
    first.write(item())

    restarted = PostgresMemoryStore(factory(database, counters))
    restored = restarted.get("mem-1", tenant_id="tenant-a")

    assert restored == item()
    assert counters["commits"] == 1


def test_get_and_delete_are_tenant_isolated():
    database, counters = {}, {"commits": 0, "rollbacks": 0, "closes": 0}
    store = PostgresMemoryStore(factory(database, counters))
    store.write(item())

    assert store.get("mem-1", tenant_id="tenant-b") is None
    assert store.delete("mem-1", tenant_id="tenant-b") is False
    assert store.get("mem-1", tenant_id="tenant-a") is not None
    assert store.delete("mem-1", tenant_id="tenant-a") is True
    assert store.get("mem-1", tenant_id="tenant-a") is None


def test_cross_tenant_memory_id_overwrite_is_rejected():
    database, counters = {}, {"commits": 0, "rollbacks": 0, "closes": 0}
    store = PostgresMemoryStore(factory(database, counters))
    store.write(item(tenant_id="tenant-a"))

    with pytest.raises(ValueError, match="tenant boundary"):
        store.write(item(tenant_id="tenant-b"))


def test_search_returns_only_requested_tenant():
    database, counters = {}, {"commits": 0, "rollbacks": 0, "closes": 0}
    store = PostgresMemoryStore(factory(database, counters))
    store.write(item(tenant_id="tenant-a", memory_id="a"))
    store.write(item(tenant_id="tenant-b", memory_id="b"))

    result = store.search(MemoryQuery(tenant_id="tenant-a"))

    assert [entry.memory_id for entry in result] == ["a"]


def test_search_sql_contains_all_supported_filters():
    class RecordingCursor(FakeCursor):
        def execute(self, sql, params=()):
            if "SELECT memory_id" in sql and "WHERE" in sql:
                self.database["sql"] = sql
                self.database["params"] = params
                self.rows = []
                return
            super().execute(sql, params)

    class RecordingConnection(FakeConnection):
        def cursor(self):
            return RecordingCursor(self.database)

    recorded, counters = {}, {"commits": 0, "rollbacks": 0, "closes": 0}
    store = PostgresMemoryStore(lambda: RecordingConnection(recorded, counters))
    store.search(MemoryQuery(
        tenant_id="tenant-a",
        scopes=(MemoryScope.MISSION,),
        memory_types=(MemoryType.DECISION,),
        mission_id="mission-1",
        execution_id="exec-1",
        user_id="user-1",
        domain="education",
        entity_id="entity-1",
        text="needle",
        min_importance=0.7,
        metadata={"source": "human"},
        limit=7,
    ))

    sql = recorded["sql"]
    assert "tenant_id = %s" in sql
    assert "scope IN (%s)" in sql
    assert "memory_type IN (%s)" in sql
    assert "mission_id = %s" in sql
    assert "execution_id = %s" in sql
    assert "user_id = %s" in sql
    assert "domain = %s" in sql
    assert "entity_id = %s" in sql
    assert "importance >= %s" in sql
    assert "POSITION(LOWER(%s) IN LOWER(content)) > 0" in sql
    assert "metadata @> %s::jsonb" in sql
    assert recorded["params"][-1] == 7


def test_ensure_schema_creates_table_and_tenant_indexes():
    statements = []

    class SchemaCursor:
        def execute(self, sql, params=()):
            statements.append(sql)
        def close(self):
            pass

    class SchemaConnection:
        def cursor(self):
            return SchemaCursor()
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    PostgresMemoryStore(lambda: SchemaConnection(), ensure_schema=True)

    joined = "\n".join(statements)
    assert "CREATE TABLE IF NOT EXISTS rkjo_memory_items" in joined
    assert "idx_rkjo_memory_tenant" in joined
    assert "idx_rkjo_memory_mission" in joined
    assert "idx_rkjo_memory_entity" in joined


@pytest.mark.parametrize("tenant_id", ["", "   "])
def test_blank_tenant_is_rejected_on_reads(tenant_id):
    store = PostgresMemoryStore(lambda: None)
    with pytest.raises(ValueError):
        store.get("mem-1", tenant_id=tenant_id)
    with pytest.raises(ValueError):
        store.delete("mem-1", tenant_id=tenant_id)
