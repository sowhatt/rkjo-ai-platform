"""PostgreSQL persistence for durable harness checkpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from rkjo_kernel.harness.state import HarnessState, HarnessStateStatus


class Cursor(Protocol):
    def execute(self, operation: str, parameters: tuple[Any, ...] = ()) -> Any: ...
    def fetchone(self) -> Any: ...
    def fetchall(self) -> list[Any]: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


ConnectionFactory = Callable[[], Connection]


class PostgresHarnessStateStore:
    TABLE = "rkjo_harness_states"

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
        self._write((
            f"""CREATE TABLE IF NOT EXISTS {self.TABLE} (
                state_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                status TEXT NOT NULL,
                iteration BIGINT NOT NULL,
                checkpoint_version BIGINT NOT NULL,
                data JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )""",
            f"CREATE INDEX IF NOT EXISTS idx_rkjo_harness_mission ON {self.TABLE} (tenant_id, mission_id, checkpoint_version DESC)",
        ))

    def save(self, state: HarnessState) -> HarnessState:
        sql = f"""INSERT INTO {self.TABLE} (
            state_id, tenant_id, mission_id, trace_id, status, iteration,
            checkpoint_version, data, metadata, created_at, updated_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)
        ON CONFLICT (state_id) DO UPDATE SET
            mission_id=EXCLUDED.mission_id,
            trace_id=EXCLUDED.trace_id,
            status=EXCLUDED.status,
            iteration=EXCLUDED.iteration,
            checkpoint_version=EXCLUDED.checkpoint_version,
            data=EXCLUDED.data,
            metadata=EXCLUDED.metadata,
            updated_at=EXCLUDED.updated_at
        WHERE {self.TABLE}.tenant_id=EXCLUDED.tenant_id
        RETURNING tenant_id"""
        row = self._returning(sql, (
            state.state_id, state.tenant_id, state.mission_id, state.trace_id,
            state.status.value, state.iteration, state.checkpoint_version,
            json.dumps(state.data, default=str),
            json.dumps(state.metadata, default=str),
            state.created_at, state.updated_at,
        ))
        if row is None:
            raise ValueError("Cannot overwrite harness state across tenant boundary")
        return state

    def get(self, state_id: str, *, tenant_id: str) -> HarnessState | None:
        self._required(tenant_id, "tenant_id")
        rows = self._query(
            f"""SELECT state_id,tenant_id,mission_id,trace_id,status,iteration,
            checkpoint_version,data,metadata,created_at,updated_at
            FROM {self.TABLE} WHERE state_id=%s AND tenant_id=%s""",
            (state_id, tenant_id),
        )
        return self._to_state(rows[0]) if rows else None

    def latest_for_mission(
        self, mission_id: str, *, tenant_id: str
    ) -> HarnessState | None:
        self._required(tenant_id, "tenant_id")
        self._required(mission_id, "mission_id")
        rows = self._query(
            f"""SELECT state_id,tenant_id,mission_id,trace_id,status,iteration,
            checkpoint_version,data,metadata,created_at,updated_at
            FROM {self.TABLE}
            WHERE tenant_id=%s AND mission_id=%s
            ORDER BY checkpoint_version DESC, updated_at DESC, state_id DESC
            LIMIT 1""",
            (tenant_id, mission_id),
        )
        return self._to_state(rows[0]) if rows else None

    def delete(self, state_id: str, *, tenant_id: str) -> bool:
        self._required(tenant_id, "tenant_id")
        return self._returning(
            f"DELETE FROM {self.TABLE} WHERE state_id=%s AND tenant_id=%s RETURNING state_id",
            (state_id, tenant_id),
        ) is not None

    @staticmethod
    def _required(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must not be empty")

    def _query(self, sql: str, params: tuple[Any, ...]) -> list[Any]:
        connection = self._connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
        finally:
            cursor.close()
            connection.close()

    def _returning(self, sql: str, params: tuple[Any, ...]) -> Any:
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

    def _write(self, statements: tuple[str, ...]) -> None:
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
    def _to_state(row: Any) -> HarnessState:
        data, metadata = row[7], row[8]
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        created_at, updated_at = row[9], row[10]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return HarnessState(
            state_id=str(row[0]), tenant_id=str(row[1]), mission_id=str(row[2]),
            trace_id=str(row[3]), status=HarnessStateStatus(row[4]),
            iteration=int(row[5]), checkpoint_version=int(row[6]),
            data=dict(data or {}), metadata=dict(metadata or {}),
            created_at=created_at, updated_at=updated_at,
        )
