"""OMNI-016.4.3 fail-closed worker heartbeat configuration."""
import pytest

from rkjo_worker.omnichannel_heartbeat import configured_publisher
from rkjo_worker.omnichannel_whatsapp_delivery import SupervisedWhatsAppDelivery


def test_unbound_worker_never_publishes_heartbeat():
    assert configured_publisher(database_url="postgresql://unused",
            worker_name="whatsapp-delivery",environ={}) is None


def test_explicit_tenant_binds_publisher():
    publisher=configured_publisher(database_url="postgresql://unused",
        worker_name="whatsapp-delivery",
        environ={"RKJO_OMNI_WORKER_TENANT_ID":"tenant-a"})
    assert publisher is not None
    assert publisher.tenant_id=="tenant-a"


def test_supervisor_emits_ready_after_success():
    statuses=[]
    class Heartbeat:
        def record(self,status):
            statuses.append(status)
    class Worker:
        def run_once(self,*,now):
            return False
    supervisor=SupervisedWhatsAppDelivery(
        worker=Worker(),heartbeat=Heartbeat(),sleep_fn=lambda _:None,
    )
    def one_iteration(_):
        supervisor.stop()
    supervisor.sleep_fn=one_iteration
    supervisor.run()
    assert statuses==["ready"]


def test_supervisor_emits_degraded_after_failure():
    statuses=[]
    class Heartbeat:
        def record(self,status):
            statuses.append(status)
    class Worker:
        def run_once(self,*,now):
            raise RuntimeError("secret must not be logged")
    supervisor=SupervisedWhatsAppDelivery(
        worker=Worker(),heartbeat=Heartbeat(),sleep_fn=lambda _:None,
    )
    supervisor.sleep_fn=lambda _:supervisor.stop()
    supervisor.run()
    assert statuses==["degraded"]
