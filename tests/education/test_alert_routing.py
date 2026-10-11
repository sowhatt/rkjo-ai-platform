from uuid import uuid4
import pytest

from rkjo_education.supervision.safety_alerts import SafetyAlert, SafetyAlertKind, dispatch_safety_alert
from rkjo_education.supervision.alert_routing import (
    InMemoryTeacherAlertSink, AlertTenantMismatch, visible_alerts,
)


def make_alert(tenant):
    return SafetyAlert(uuid4(), tenant, uuid4(), uuid4(), SafetyAlertKind.UNSAFE_CONTENT)


def test_direct_dispatch_without_proof_repository():
    tenant = uuid4()
    sink = InMemoryTeacherAlertSink(tenant)
    alert = make_alert(tenant)
    dispatch_safety_alert(alert, sink)
    assert visible_alerts(sink, viewer_tenant_id=tenant) == (alert,)


def test_duplicate_alert_id_is_idempotent():
    tenant = uuid4()
    sink = InMemoryTeacherAlertSink(tenant)
    alert = make_alert(tenant)
    dispatch_safety_alert(alert, sink)
    dispatch_safety_alert(alert, sink)
    assert len(sink.delivered) == 1


def test_cross_tenant_alert_rejected():
    sink = InMemoryTeacherAlertSink(uuid4())
    with pytest.raises(AlertTenantMismatch):
        dispatch_safety_alert(make_alert(uuid4()), sink)
    assert sink.delivered == []


def test_cross_tenant_viewer_rejected():
    sink = InMemoryTeacherAlertSink(uuid4())
    with pytest.raises(AlertTenantMismatch):
        visible_alerts(sink, viewer_tenant_id=uuid4())
