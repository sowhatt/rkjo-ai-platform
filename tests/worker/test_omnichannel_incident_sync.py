"""OMNI-016.4 sync CLI operational and redaction tests."""
import json

from rkjo_worker import omnichannel_incident_sync as cli


def test_sync_success_no_alerts(monkeypatch,capsys):
    monkeypatch.setenv("RKJO_DATABASE_URL","postgresql://dummy")
    monkeypatch.setattr(cli,"sync_tenant",lambda **kw: {
        "tenant_id":kw["tenant_id"],"active_alerts":0,
        "critical":False,"healthy":True,
    })
    assert cli.main(["--tenant-id","tenant-a"])==0
    assert json.loads(capsys.readouterr().out)["healthy"]


def test_sync_alerts_returns_nonzero(monkeypatch,capsys):
    monkeypatch.setenv("RKJO_DATABASE_URL","postgresql://dummy")
    monkeypatch.setattr(cli,"sync_tenant",lambda **kw: {
        "tenant_id":kw["tenant_id"],"active_alerts":2,
        "critical":True,"healthy":False,
    })
    assert cli.main(["--tenant-id","tenant-a"])==2
    assert json.loads(capsys.readouterr().out)["active_alerts"]==2


def test_sync_errors_do_not_expose_dsn(monkeypatch,capsys):
    monkeypatch.setenv("RKJO_DATABASE_URL","postgresql://secret-token")
    def fail(**kw):
        raise RuntimeError("postgresql://secret-token")
    monkeypatch.setattr(cli,"sync_tenant",fail)
    assert cli.main(["--tenant-id","tenant-a"])==3
    captured=capsys.readouterr().out
    assert "secret-token" not in captured
    assert json.loads(captured)=={"error":"OmnichannelIncidentSyncUnavailable"}
