"""OMNI-016.4 incident lifecycle on isolated PostgreSQL."""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.incidents import PostgreSQLOmnichannelIncidents
from rkjo_kernel.omnichannel.monitoring import (
    AlertSeverity, OmnichannelAlert, OmnichannelMonitoringReport,
)


NOW=datetime(2026,10,10,12,tzinfo=timezone.utc)


@pytest.fixture
def journal():
    url=os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires RKJO_TEST_DATABASE_URL")
    if "test" not in conninfo_to_dict(url).get("dbname","").lower():
        pytest.fail("Dedicated test DB only")
    schema="rkjo_omni_incidents_"+uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "'+schema+'"')
    scoped=make_conninfo(url,options="-c search_path="+schema)
    try:
        obj=PostgreSQLOmnichannelIncidents(scoped)
        obj.initialize_schema()
        yield obj
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "'+schema+'" CASCADE')


def report(*, tenant="t1", at=NOW, count=2, include=True):
    alerts=(OmnichannelAlert(tenant,"OUTBOUND_FAILED",AlertSeverity.CRITICAL,
                              count,"Failed outbound deliveries"),) if include else ()
    return OmnichannelMonitoringReport(tenant,at,alerts)


def test_sync_deduplicates_and_updates_counts(journal):
    assert journal.sync(report())==1
    assert journal.sync(report(at=NOW+timedelta(minutes=1),count=3))==1
    rows=journal.list(tenant_id="t1")
    assert len(rows)==1
    assert rows[0].count==3
    assert rows[0].status=="open"
    assert rows[0].first_seen_at==NOW


def test_acknowledge_is_operator_bound_and_idempotency_is_explicit(journal):
    journal.sync(report())
    item=journal.acknowledge(tenant_id="t1",code="OUTBOUND_FAILED",
                             operator_id="operator-1",at=NOW)
    assert item.status=="acknowledged"
    assert item.acknowledged_by=="operator-1"
    with pytest.raises(LookupError):
        journal.acknowledge(tenant_id="t1",code="OUTBOUND_FAILED",
                             operator_id="operator-2",at=NOW)


def test_empty_report_resolves_and_new_occurrence_reopens(journal):
    journal.sync(report())
    journal.acknowledge(tenant_id="t1",code="OUTBOUND_FAILED",
                        operator_id="operator-1",at=NOW)
    journal.sync(report(include=False,at=NOW+timedelta(minutes=1)))
    assert journal.list(tenant_id="t1")==[]
    assert journal.list(tenant_id="t1",include_resolved=True)[0].status=="resolved"
    journal.sync(report(at=NOW+timedelta(minutes=2)))
    reopened=journal.list(tenant_id="t1")[0]
    assert reopened.status=="open"
    assert reopened.acknowledged_by is None


def test_stale_report_does_not_resolve_newer_incident(journal):
    journal.sync(report(at=NOW+timedelta(minutes=2)))
    journal.sync(report(include=False,at=NOW))
    assert journal.list(tenant_id="t1")[0].status=="open"


def test_other_tenant_cannot_read_acknowledge_or_modify(journal):
    journal.sync(report())
    assert journal.list(tenant_id="t2")==[]
    with pytest.raises(LookupError):
        journal.acknowledge(tenant_id="t2",code="OUTBOUND_FAILED",
                             operator_id="operator-1")
    journal.sync(report(tenant="t2",count=5))
    assert journal.list(tenant_id="t1")[0].count==2


def test_cross_tenant_report_and_duplicate_codes_denied(journal):
    alert=OmnichannelAlert("t2","OUTBOUND_FAILED",AlertSeverity.CRITICAL,1,"x")
    with pytest.raises(PermissionError):
        journal.sync(OmnichannelMonitoringReport("t1",NOW,(alert,)))
    a=OmnichannelAlert("t1","OUTBOUND_FAILED",AlertSeverity.CRITICAL,1,"x")
    with pytest.raises(ValueError):
        journal.sync(OmnichannelMonitoringReport("t1",NOW,(a,a)))


def test_invalid_acknowledgement_rejected(journal):
    journal.sync(report())
    with pytest.raises(ValueError):
        journal.acknowledge(tenant_id="t1",code="OUTBOUND_FAILED",
                            operator_id="")
