"""OMNI-016.4.3 tenant scoped heartbeat tests against isolated PostgreSQL."""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.worker_heartbeats import PostgreSQLOmnichannelWorkerHeartbeats

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


@pytest.fixture
def store():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required")
    if "test" not in conninfo_to_dict(url).get("dbname","").lower():
        pytest.fail("Dedicated test DB required")
    schema = "rkjo_omni_worker_health_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "'+schema+'"')
    scoped = make_conninfo(url, options="-c search_path="+schema)
    try:
        result = PostgreSQLOmnichannelWorkerHeartbeats(scoped)
        result.initialize_schema()
        yield result
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "'+schema+'" CASCADE')


def test_tenant_isolation_and_stale_detection(store):
    store.beat(tenant_id="a",worker_name="dispatcher",status="ready",at=NOW)
    store.beat(tenant_id="b",worker_name="dispatcher",status="degraded",at=NOW)
    assert len(store.list(tenant_id="a",now=NOW))==1
    assert store.list(tenant_id="a",now=NOW)[0].status=="ready"
    assert store.list(tenant_id="a",now=NOW+timedelta(seconds=91))[0].stale
    assert store.list(tenant_id="b",now=NOW)[0].status=="degraded"
    assert store.list(tenant_id="c",now=NOW)==[]


def test_older_heartbeat_does_not_rewind_state(store):
    store.beat(tenant_id="a",worker_name="delivery",status="ready",at=NOW)
    store.beat(tenant_id="a",worker_name="delivery",status="degraded",
               at=NOW-timedelta(minutes=1))
    assert store.list(tenant_id="a",now=NOW)[0].status=="ready"


@pytest.mark.parametrize("bad",["", " ", "worker/other", "worker?query", "."])
def test_invalid_worker_name_rejected(store,bad):
    with pytest.raises(ValueError):
        store.beat(tenant_id="a",worker_name=bad,status="ready",at=NOW)


def test_naive_clock_and_unbound_tenant_rejected(store):
    with pytest.raises(ValueError):
        store.beat(tenant_id="",worker_name="dispatcher",status="ready",at=NOW)
    with pytest.raises(ValueError):
        store.beat(tenant_id="a",worker_name="dispatcher",status="ready",
                   at=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        store.list(tenant_id="a",now=NOW,stale_after_seconds=0)
