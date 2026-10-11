"""Durable local safety alert outbox, independent of learning proofs.

Reference SQLite implementation for tests/development. Production needs
PostgreSQL transaction/outbox, authorized consumers and real event delivery.
"""
import sqlite3
from uuid import UUID

from rkjo_education.supervision.safety_alerts import SafetyAlert, SafetyAlertKind


class AlertOutboxDenied(PermissionError):
    pass


class SqliteSafetyAlertOutbox:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def initialize(self) -> None:
        with sqlite3.connect(self.db_path, timeout=10) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS education_safety_alert_outbox (
                alert_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL, session_id TEXT NOT NULL,
                learner_id TEXT NOT NULL, kind TEXT NOT NULL,
                requires_teacher_attention INTEGER NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0
            )""")

    def publish(self, alert: SafetyAlert) -> None:
        if not isinstance(alert.kind, SafetyAlertKind):
            raise ValueError("Invalid alert kind")
        with sqlite3.connect(self.db_path, timeout=10) as db:
            db.execute(
                """INSERT OR IGNORE INTO education_safety_alert_outbox
                   (alert_id,tenant_id,session_id,learner_id,kind,requires_teacher_attention)
                   VALUES (?,?,?,?,?,?)""",
                (str(alert.alert_id), str(alert.tenant_id), str(alert.session_id),
                 str(alert.learner_id), alert.kind.value, int(alert.requires_teacher_attention)),
            )
            row = db.execute(
                "SELECT tenant_id FROM education_safety_alert_outbox WHERE alert_id=?",
                (str(alert.alert_id),),
            ).fetchone()
            if row[0] != str(alert.tenant_id):
                raise AlertOutboxDenied("Alert id already registered under another tenant")

    def pending(self, *, tenant_id: UUID) -> tuple[SafetyAlert, ...]:
        """Caller MUST have tenant permission checked by the API boundary."""
        with sqlite3.connect(self.db_path, timeout=10) as db:
            rows = db.execute(
                """SELECT alert_id,session_id,learner_id,kind,requires_teacher_attention
                   FROM education_safety_alert_outbox
                   WHERE tenant_id=? AND acknowledged=0 ORDER BY rowid""",
                (str(tenant_id),),
            ).fetchall()
        return tuple(
            SafetyAlert(UUID(r[0]), tenant_id, UUID(r[1]), UUID(r[2]),
                        SafetyAlertKind(r[3]), bool(r[4])) for r in rows
        )

    def acknowledge(self, *, alert_id: UUID, tenant_id: UUID) -> bool:
        """Returns false if absent or belongs to another tenant."""
        with sqlite3.connect(self.db_path, timeout=10) as db:
            result = db.execute(
                """UPDATE education_safety_alert_outbox SET acknowledged=1
                   WHERE alert_id=? AND tenant_id=? AND acknowledged=0""",
                (str(alert_id), str(tenant_id)),
            )
            return result.rowcount == 1
