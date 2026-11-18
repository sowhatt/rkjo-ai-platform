"""OMNI-016.4 — durable tenant-scoped incident journal.

The monitor remains read-only. Persist evaluated alerts separately using a
deduplicated incident lifecycle. Acknowledgement never resends notifications.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg

from rkjo_kernel.omnichannel.monitoring import OmnichannelMonitoringReport


@dataclass(frozen=True, slots=True)
class Incident:
    tenant_id: str
    code: str
    severity: str
    status: str
    count: int
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged_by: str | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None


def _incident(row) -> Incident:
    return Incident(*row)


_COLS = ("tenant_id,code,severity,status,count,first_seen_at,"
         "last_seen_at,acknowledged_by,acknowledged_at,resolved_at")


class PostgreSQLOmnichannelIncidents:
    def __init__(self, database_url: str):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url

    def initialize_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS omni_operational_incidents (
                    tenant_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    severity TEXT NOT NULL CHECK (severity IN ('warning','critical')),
                    status TEXT NOT NULL CHECK (status IN ('open','acknowledged','resolved')),
                    count INTEGER NOT NULL CHECK (count >= 1),
                    first_seen_at TIMESTAMPTZ NOT NULL,
                    last_seen_at TIMESTAMPTZ NOT NULL,
                    acknowledged_by TEXT,
                    acknowledged_at TIMESTAMPTZ,
                    resolved_at TIMESTAMPTZ,
                    PRIMARY KEY (tenant_id,code)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_omni_incidents_status
                ON omni_operational_incidents (tenant_id,status,last_seen_at DESC)
            """)

    def sync(self, report: OmnichannelMonitoringReport) -> int:
        """Atomically upsert observed alerts and resolve absent ones.

        The stale-report guard prevents a delayed monitor from rewinding newer
        observations. No remote notifications or message delivery actions.
        """
        if not report.tenant_id.strip() or report.evaluated_at.utcoffset() is None:
            raise ValueError("Tenant and timezone-aware report required.")
        if any(a.tenant_id != report.tenant_id for a in report.alerts):
            raise PermissionError("Cross-tenant alert rejected.")
        codes = [a.code for a in report.alerts]
        if len(set(codes)) != len(codes):
            raise ValueError("Duplicate codes in monitoring report.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # Serialize monitors for the same tenant (including empty reports).
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                            ("omni_incidents:"+report.tenant_id,))
                for a in report.alerts:
                    cur.execute("""
                        INSERT INTO omni_operational_incidents
                          (tenant_id,code,severity,status,count,first_seen_at,last_seen_at)
                        VALUES (%s,%s,%s,'open',%s,%s,%s)
                        ON CONFLICT (tenant_id,code) DO UPDATE SET
                          severity=EXCLUDED.severity, count=EXCLUDED.count,
                          last_seen_at=EXCLUDED.last_seen_at,
                          status=CASE WHEN omni_operational_incidents.status='resolved'
                            THEN 'open' ELSE omni_operational_incidents.status END,
                          first_seen_at=CASE WHEN omni_operational_incidents.status='resolved'
                            THEN EXCLUDED.first_seen_at
                            ELSE omni_operational_incidents.first_seen_at END,
                          acknowledged_by=CASE WHEN omni_operational_incidents.status='resolved'
                            THEN NULL ELSE omni_operational_incidents.acknowledged_by END,
                          acknowledged_at=CASE WHEN omni_operational_incidents.status='resolved'
                            THEN NULL ELSE omni_operational_incidents.acknowledged_at END,
                          resolved_at=NULL
                        WHERE omni_operational_incidents.last_seen_at<=EXCLUDED.last_seen_at
                    """, (report.tenant_id,a.code,a.severity.value,a.count,
                          report.evaluated_at,report.evaluated_at))
                cur.execute("""
                    UPDATE omni_operational_incidents
                    SET status='resolved',resolved_at=%s
                    WHERE tenant_id=%s AND status!='resolved'
                      AND last_seen_at<=%s AND NOT (code=ANY(%s::text[]))
                """, (report.evaluated_at,report.tenant_id,report.evaluated_at,codes))
        return len(report.alerts)

    def list(self, *, tenant_id: str, include_resolved: bool = False,
             limit: int = 100) -> list[Incident]:
        if not tenant_id or not tenant_id.strip() or not 1 <= limit <= 500:
            raise ValueError("Valid tenant and bounded limit required.")
        with psycopg.connect(self.database_url) as conn:
            rows = conn.execute(f"""
                SELECT {_COLS} FROM omni_operational_incidents
                WHERE tenant_id=%s AND (%s OR status!='resolved')
                ORDER BY last_seen_at DESC, code LIMIT %s
            """, (tenant_id,include_resolved,limit)).fetchall()
        return [_incident(r) for r in rows]

    def acknowledge(self, *, tenant_id: str, code: str,
                    operator_id: str, at: datetime | None = None) -> Incident:
        at = at or datetime.now(timezone.utc)
        if not all(isinstance(v,str) and v.strip() for v in (tenant_id,code,operator_id)):
            raise ValueError("Tenant, incident code and operator identity required.")
        if at.utcoffset() is None:
            raise ValueError("Timezone-aware acknowledgement required.")
        with psycopg.connect(self.database_url) as conn:
            row=conn.execute(f"""
                UPDATE omni_operational_incidents
                SET status='acknowledged', acknowledged_by=%s, acknowledged_at=%s
                WHERE tenant_id=%s AND code=%s AND status='open'
                RETURNING {_COLS}
            """, (operator_id,at,tenant_id,code)).fetchone()
            if row is None:
                raise LookupError("Open incident not found.")
            return _incident(row)
