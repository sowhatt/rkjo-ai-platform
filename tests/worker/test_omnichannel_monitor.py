"""OMNI-016.3 monitoring CLI does not leak DSNs or exceptions."""
import json

from rkjo_worker import omnichannel_monitor as cli


def test_probe_healthy_exit(monkeypatch,capsys):
    monkeypatch.setenv("RKJO_DATABASE_URL","postgresql://test-secret")
    monkeypatch.setattr(cli,"probe",lambda **_: {
        "healthy":True,"has_critical":False,"alerts":[],
    })
    assert cli.main(["--tenant-id","tenant-a"])==0
    assert json.loads(capsys.readouterr().out)["healthy"] is True


def test_probe_warning_exit(monkeypatch,capsys):
    monkeypatch.setenv("RKJO_DATABASE_URL","postgresql://test-secret")
    monkeypatch.setattr(cli,"probe",lambda **_: {
        "healthy":False,"has_critical":False,
        "alerts":[{"code":"INBOUND_BACKLOG","count":100}],
    })
    assert cli.main(["--tenant-id","tenant-a"])==2
    assert json.loads(capsys.readouterr().out)["alerts"][0]["count"]==100


def test_probe_failure_redacts_database_details(monkeypatch,capsys):
    monkeypatch.setenv("RKJO_DATABASE_URL","postgresql://secret-password")
    def explode(**kwargs):
        raise RuntimeError("postgresql://secret-password")
    monkeypatch.setattr(cli,"probe",explode)
    assert cli.main(["--tenant-id","tenant-a"])==3
    output=capsys.readouterr().out
    assert "secret-password" not in output
    assert json.loads(output)=={
        "healthy":False,"error":"OmnichannelProbeUnavailable",
    }


def test_invalid_threshold_exits_without_probe(monkeypatch,capsys):
    monkeypatch.setenv("RKJO_DATABASE_URL","postgresql://test-secret")
    def forbidden(**kwargs):
        raise AssertionError("Must fail before DB probe")
    monkeypatch.setattr(cli,"probe",forbidden)
    assert cli.main(["--tenant-id","tenant-a","--outbound-backlog","0"])==3
    assert json.loads(capsys.readouterr().out)["error"]=="OmnichannelProbeUnavailable"
