from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from .models import MemoryItem, MemoryQuery, MemoryScope, MemoryType


class DBAPICursor(Protocol):
    def execute(self, operation: str, parameters: tuple[Any, ...] = ()) -> Any: ...
    def fetchone(self) -> Any: ...
    def fetchall(self) -> list[Any]: ...
    def close(self) -> None: ...


class DBAPIConnection(Protocol):
    def cursor(self) -> DBAPICursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


ConnectionFactory = Callable[[], DBAPIConnection]


class PostgresMemoryStore:
    """Durable PostgreSQL implementation of MemoryPort.

    The kernel depends only on a PEP-249-style connection factory. Applications
    can therefore supply psycopg/psycopg2 without making the kernel own a
    database driver or connection pool.
    """

    TABLE = "rkjo_memory_items"

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        ensure_schema: bool = False,
    ) -> None:
        self._connection_factory = connection_factory
        if ensure_schema:
            self.ensure_schema()

    def ensure_schema(self) -> None:
        statements = (
            f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE} (
                memory_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                mission_id TEXT NULL,
                execution_id TEXT NULL,
                user_id TEXT NULL,
                domain TEXT NULL,
                entity_id TEXT NULL,
                importance DOUBLE PRECISION NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL
            )
            """,
            f"CREATE INDEX IF NOT EXISTS idx_rkjo_memory_tenant ON {self.TABLE} (tenant_id)",
            f"CREATE INDEX IF NOT EXISTS idx_rkjo_memory_mission ON {self.TABLE} (tenant_id, mission_id)",
            f"CREATE INDEX IF NOT EXISTS idx_rkjo_memory_entity ON {self.TABLE} (tenant_id, entity_id)",
            f"CREATE INDEX IF NOT EXISTS idx_rkjo_memory_created ON {self.TABLE} (tenant_id, created_at DESC)",
        )
        self._write_transaction(statements)

    def write(self, item: MemoryItem) -> MemoryItem:
        sql = f"""
        INSERT INTO {self.TABLE} (
            memory_id, tenant_id, scope, memory_type, content,
            mission_id, execution_id, user_id, domain, entity_id,
            importance, metadata, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (memory_id) DO UPDATE SET
            scope = EXCLUDED.scope,
            memory_type = EXCLUDED.memory_type,
            content = EXCLUDED.content,
            mission_id = EXCLUDED.mission_id,
            execution_id = EXCLUDED.execution_id,
            user_id = EXCLUDED.user_id,
            domain = EXCLUDED.domain,
            entity_id = EXCLUDED.entity_id,
            importance = EXCLUDED.importance,
            metadata = EXCLUDED.metadata,
            created_at = EXCLUDED.created_at
        WHERE {self.TABLE}.tenant_id = EXCLUDED.tenant_id
        RETURNING tenant_id
        """
        params = (
            item.memory_id,
            item.tenant_id,
            item.scope.value,
            item.memory_type.value,
            item.content,
            item.mission_id,
            item.execution_id,
            item.user_id,
            item.domain,
            item.entity_id,
            item.importance,
            json.dumps(item.metadata, separators=(",", ":"), default=str),
            item.created_at,
        )
        row = self._execute_returning_one(sql, params)
        if row is None:
            raise ValueError("Cannot overwrite memory across tenant boundary")
        return item

    def get(self, memory_id: str, *, tenant_id: str) -> MemoryItem | None:
        self._validate_tenant(tenant_id)
        sql = f"""
        SELECT memory_id, tenant_id, scope, memory_type, content,
               mission_id, execution_id, user_id, domain, entity_id,
               importance, metadata, created_at
        FROM {self.TABLE}
        WHERE memory_id = %s AND tenant_id = %s
        """
        rows = self._query(sql, (memory_id, tenant_id))
        return self._to_item(rows[0]) if rows else None

    def search(self, query: MemoryQuery) -> list[MemoryItem]:
        clauses = ["tenant_id = %s"]
        params: list[Any] = [query.tenant_id]

        self._add_in_filter(clauses, params, "scope", tuple(x.value for x in query.scopes))
        self._add_in_filter(
            clauses, params, "memory_type", tuple(x.value for x in query.memory_types)
        )
        for column, value in (
            ("mission_id", query.mission_id),
            ("execution_id", query.execution_id),
            ("user_id", query.user_id),
            ("domain", query.domain),
            ("entity_id", query.entity_id),
        ):
            if value is not None:
                clauses.append(f"{column} = %s")
                params.append(value)

        if query.min_importance is not None:
            clauses.append("importance >= %s")
            params.append(query.min_importance)
        if query.text and query.text.strip():
            clauses.append("POSITION(LOWER(%s) IN LOWER(content)) > 0")
            params.append(query.text.strip())
        if query.metadata:
            clauses.append("metadata @> %s::jsonb")
            params.append(json.dumps(query.metadata, separators=(",", ":"), default=str))

        params.append(query.limit)
        sql = f"""
        SELECT memory_id, tenant_id, scope, memory_type, content,
               mission_id, execution_id, user_id, domain, entity_id,
               importance, metadata, created_at
        FROM {self.TABLE}
        WHERE {" AND ".join(clauses)}
        ORDER BY importance DESC, created_at DESC, memory_id DESC
        LIMIT %s
        """
        return [self._to_item(row) for row in self._query(sql, tuple(params))]

    def delete(self, memory_id: str, *, tenant_id: str) -> bool:
        self._validate_tenant(tenant_id)
        sql = f"""
        DELETE FROM {self.TABLE}
        WHERE memory_id = %s AND tenant_id = %s
        RETURNING memory_id
        """
        return self._execute_returning_one(sql, (memory_id, tenant_id)) is not None

    @staticmethod
    def _validate_tenant(tenant_id: str) -> None:
        if not tenant_id.strip():
            raise ValueError("tenant_id must not be empty")

    @staticmethod
    def _add_in_filter(
        clauses: list[str],
        params: list[Any],
        column: str,
        values: tuple[str, ...],
    ) -> None:
        if not values:
            return
        placeholders = ", ".join("%s" for _ in values)
        clauses.append(f"{column} IN ({placeholders})")
        params.extend(values)

    def _query(self, sql: str, params: tuple[Any, ...]) -> list[Any]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
        finally:
            cursor.close()
            connection.close()

    def _execute_returning_one(self, sql: str, params: tuple[Any, ...]) -> Any:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            connection.commit()
            return row
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def _write_transaction(self, statements: tuple[str, ...]) -> None:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            for statement in statements:
                cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _to_item(row: Any) -> MemoryItem:
        metadata = row[11]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        created_at = row[12]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return MemoryItem(
            memory_id=str(row[0]),
            tenant_id=str(row[1]),
            scope=MemoryScope(row[2]),
            memory_type=MemoryType(row[3]),
            content=str(row[4]),
            mission_id=row[5],
            execution_id=row[6],
            user_id=row[7],
            domain=row[8],
            entity_id=row[9],
            importance=float(row[10]),
            metadata=dict(metadata or {}),
            created_at=created_at,
        )
