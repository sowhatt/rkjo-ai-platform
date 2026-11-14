import json
import xml.etree.ElementTree as ET

from scripts.l1_ci_summary import EXPECTED_L1, summarize


def report(tmp_path, monkeypatch):
    lock = tmp_path / "requirements.txt"
    lock.write_text("example==1.0\n")
    monkeypatch.setattr("scripts.l1_ci_summary.importlib.metadata.version", lambda _: "1.0")
    root = ET.Element("testsuite")
    for name in sorted(EXPECTED_L1):
        classname, function = name.rsplit(".", 1)
        case = ET.SubElement(root, "testcase", classname=classname, name=function, time="0.01")
        ET.SubElement(case, "system-out").text = "private-hostname sensitive-test-payload"
    path = tmp_path / "results.xml"
    ET.ElementTree(root).write(path)
    return root, path, lock


def test_l1_summary_requires_all_cases_and_omits_raw_output(tmp_path, monkeypatch):
    _, path, lock = report(tmp_path, monkeypatch)
    result = summarize("l1", path, lock)
    assert result["qualified"] and result["counts"]["passed"] == 8
    assert "private-hostname" not in json.dumps(result)
    assert "sensitive-test-payload" not in json.dumps(result)


def test_l1_summary_rejects_skipped_or_missing_test(tmp_path, monkeypatch):
    root, path, lock = report(tmp_path, monkeypatch)
    ET.SubElement(root[0], "skipped")
    ET.ElementTree(root).write(path)
    assert not summarize("l1", path, lock)["qualified"]
    root.remove(root[0])
    ET.ElementTree(root).write(path)
    assert "expected_eight_named_l1_tests_not_executed" in summarize("l1", path, lock)["issues"]


def test_l1_summary_rejects_dependency_drift(tmp_path, monkeypatch):
    _, path, lock = report(tmp_path, monkeypatch)
    monkeypatch.setattr("scripts.l1_ci_summary.importlib.metadata.version", lambda _: "2.0")
    result = summarize("l1", path, lock)
    assert not result["qualified"]
    assert result["issues"] == ["dependency_lock_mismatch:example"]


def test_summary_drops_parametrized_data_and_failure_content(tmp_path, monkeypatch):
    root, path, lock = report(tmp_path, monkeypatch)
    root[0].set("name", "test_example[sensitive-argument]")
    ET.SubElement(root[0], "failure", message="private-failure-detail").text = "private-traceback"
    ET.ElementTree(root).write(path)
    result = summarize("regression", path, lock)
    assert not result["qualified"]
    serialized = json.dumps(result)
    assert all(value not in serialized for value in ["sensitive-argument", "private-failure-detail", "private-traceback"])
