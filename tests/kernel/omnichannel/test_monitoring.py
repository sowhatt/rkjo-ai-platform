"""OMNI-016.3 operational alert decisions and tenant-safe outputs."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from rkjo_kernel.omnichannel.monitoring import (
    AlertSeverity, AlertThresholds, PostgreSQLOmnichannelMonitor,
    evaluate_snapshot,
)
from rkjo_kernel.omnichannel.operations import OperationalSnapshot, QueueHealth


NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
ZERO = QueueHealth(pending=0, failed=0, expired_leases=0)


def snapshot(**values):
    data = {
        "tenant_id":"tenant-a", "inbound":ZERO, "routes":ZERO,
        "outbound":ZERO, "uncertain_outbound":0,
        "provider_confirmed_uncommitted":0, "sent_without_binding":0,
        "delivery_receipts":0,
    }
    data.update(values)
    return OperationalSnapshot(**data)


def test_clean_snapshot_is_healthy():
    result=evaluate_snapshot(snapshot(),now=NOW)
    assert result.healthy
    assert not result.has_critical
    assert result.alerts==()
    assert result.evaluated_at==NOW


@pytest.mark.parametrize("field,code",[
    ("inbound","INBOUND_BACKLOG"),
    ("routes","ROUTE_BACKLOG"),
    ("outbound","OUTBOUND_BACKLOG"),
])
def test_backlog_is_warning_only_when_threshold_reached(field,code):
    t=AlertThresholds(inbound_backlog=3,route_backlog=3,outbound_backlog=3)
    below=evaluate_snapshot(snapshot(**{field:QueueHealth(2,0,0)}),
                            thresholds=t,now=NOW)
    assert below.alerts==()
    above=evaluate_snapshot(snapshot(**{field:QueueHealth(3,0,0)}),
                            thresholds=t,now=NOW)
    assert [(x.code,x.severity,x.count) for x in above.alerts]==[
        (code,AlertSeverity.WARNING,3),
    ]
    assert not above.has_critical


@pytest.mark.parametrize("field,code",[
    ("inbound","INBOUND_FAILED"),
    ("routes","ROUTE_FAILED"),
    ("outbound","OUTBOUND_FAILED"),
])
def test_any_failed_job_is_critical(field,code):
    result=evaluate_snapshot(
        snapshot(**{field:QueueHealth(0,1,0)}),now=NOW,
    )
    assert result.has_critical
    assert [a.code for a in result.alerts]==[code]


@pytest.mark.parametrize("field,code",[
    ("inbound","INBOUND_EXPIRED_LEASE"),
    ("routes","ROUTE_EXPIRED_LEASE"),
    ("outbound","OUTBOUND_EXPIRED_LEASE"),
])
def test_any_expired_lease_is_critical(field,code):
    result=evaluate_snapshot(
        snapshot(**{field:QueueHealth(0,0,1)}),now=NOW,
    )
    assert [a.code for a in result.alerts]==[code]


@pytest.mark.parametrize("field,code",[
    ("uncertain_outbound","UNCERTAIN_OUTBOUND"),
    ("provider_confirmed_uncommitted","PROVIDER_CONFIRMED_UNCOMMITTED"),
    ("sent_without_binding","SENT_WITHOUT_BINDING"),
])
def test_provider_proof_anomalies_are_critical(field,code):
    result=evaluate_snapshot(snapshot(**{field:1}),now=NOW)
    assert result.has_critical
    assert [a.code for a in result.alerts]==[code]


def test_multiple_alerts_stable_keys_and_no_sensitive_content():
    result=evaluate_snapshot(snapshot(
        tenant_id="tenant-a",
        inbound=QueueHealth(200,1,1),
        uncertain_outbound=2,
        delivery_receipts=123,
    ),now=NOW)
    assert result.has_critical
    keys=[a.dedup_key for a in result.alerts]
    assert len(keys)==len(set(keys))
    assert all(key.startswith("omnichannel:tenant-a:") for key in keys)
    assert "delivery_receipts" not in repr(result)


@pytest.mark.parametrize("bad",[
    {"inbound_backlog":0}, {"route_backlog":-1},
    {"outbound_backlog":True}, {"outbound_backlog":1.5},
])
def test_invalid_thresholds_are_rejected(bad):
    with pytest.raises(ValueError):
        AlertThresholds(**bad)


def test_naive_clock_and_blank_tenant_rejected():
    with pytest.raises(ValueError):
        evaluate_snapshot(snapshot(),now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        evaluate_snapshot(snapshot(tenant_id=" "),now=NOW)


def test_monitor_queries_exactly_one_tenant():
    class Operations:
        def __init__(self):
            self.calls=[]
        def snapshot(self, *, tenant_id, now):
            self.calls.append((tenant_id,now))
            return snapshot(tenant_id=tenant_id)
    operations=Operations()
    report=PostgreSQLOmnichannelMonitor(operations=operations).check(
        tenant_id="tenant-b",now=NOW,
    )
    assert report.tenant_id=="tenant-b"
    assert operations.calls==[("tenant-b",NOW)]
