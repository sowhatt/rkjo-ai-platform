from uuid import uuid4
import pytest

from rkjo_education.supervision.safety_alerts import SafetyAlert, SafetyAlertKind, dispatch_safety_alert
from rkjo_education.supervision.sqlite_alert_outbox import SqliteSafetyAlertOutbox, AlertOutboxDenied


def test_alert_is_persisted_and_visible_after_reopen(tmp_path):
    path = str(tmp_path / "alerts.db")
    sink = SqliteSafetyAlertOutbox(path)
    sink.initialize()
    tenant = uuid4()
    alert = SafetyAlert(uuid4(), tenant, uuid4(), uuid4(), SafetyAlertKind.UNSAFE_CONTENT)
    dispatch_safety_alert(alert, sink)
    reopened = SqliteSafetyAlertOutbox(path)
    assert reopened.pending(tenant_id=tenant) == (alert,)


def test_alert_idempotency_and_tenant_boundary(tmp_path):
    sink = SqliteSafetyAlertOutbox(str(tmp_path / "alerts.db"))
    sink.initialize()
    tenant = uuid4()
    alert = SafetyAlert(uuid4(), tenant, uuid4(), uuid4(), SafetyAlertKind.CONTENT_FILTER_ERROR)
    sink.publish(alert)
    sink.publish(alert)
    assert len(sink.pending(tenant_id=tenant)) == 1
    assert sink.pending(tenant_id=uuid4()) == ()
    with pytest.raises(AlertOutboxDenied):
        sink.publish(SafetyAlert(alert.alert_id, uuid4(), uuid4(), uuid4(), alert.kind))


def test_acknowledgement_tenant_scoped(tmp_path):
    sink = SqliteSafetyAlertOutbox(str(tmp_path / "alerts.db"))
    sink.initialize()
    tenant = uuid4()
    alert = SafetyAlert(uuid4(), tenant, uuid4(), uuid4(), SafetyAlertKind.UNSAFE_CONTENT)
    sink.publish(alert)
    assert not sink.acknowledge(alert_id=alert.alert_id, tenant_id=uuid4())
    assert sink.acknowledge(alert_id=alert.alert_id, tenant_id=tenant)
    assert not sink.acknowledge(alert_id=alert.alert_id, tenant_id=tenant)
    assert sink.pending(tenant_id=tenant) == ()
