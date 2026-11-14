"""Validate actual CI execution; publish only allowlisted, non-sensitive facts.

Raw JUnit can contain captured process output, paths and exception data. It stays
on the ephemeral runner. This summary copies no output, properties or failures.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


EXPECTED_L1 = {
    "tests.l1.test_acceptance.test_two_steps_restart_and_insert_only",
    "tests.l1.test_acceptance.test_concurrent_start_crash_before_publish",
    "tests.l1.test_acceptance.test_absent_worker_and_sql_rollback_leave_pending",
    "tests.l1.test_acceptance.test_http_authority_refusals",
    "tests.l1.test_acceptance.test_forged_requests_results_then_legitimate_retry",
    "tests.l1.test_acceptance.test_commit_before_ack_redelivery_and_duplicate_result",
    "tests.l1.test_acceptance.test_legitimate_broker_retry_after_result_transaction_failure",
    "tests.l1.test_security_contracts.test_tool_boundary_preserves_server_identity_over_step_metadata",
}


def summarize(suite, junit, lockfile):
    issues = []
    dependencies = []
    for line in Path(lockfile).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, pinned = line.split("==")
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        dependencies.append({"package": name, "pinned": pinned, "installed": installed})
        if installed != pinned:
            issues.append("dependency_lock_mismatch:" + name)
    cases = []
    try:
        for case in ET.parse(junit).getroot().iter("testcase"):
            # Parametrized values can be data; publish only the source test name.
            name = case.get("classname", "") + "." + case.get("name", "").split("[", 1)[0]
            status = next((tag for tag in ("failure", "error", "skipped")
                           if case.find(tag) is not None), "passed")
            # Test identifiers are fixed repository names, never request data.
            cases.append({"test": name, "status": status, "seconds": float(case.get("time", 0))})
    except (OSError, ET.ParseError, ValueError):
        issues.append("missing_or_invalid_junit")
    counts = {status: sum(c["status"] == status for c in cases)
              for status in ("passed", "failure", "error", "skipped")}
    if not cases or any(counts[s] for s in ("failure", "error", "skipped")):
        issues.append("incomplete_or_unsuccessful_execution")
    if suite == "l1":
        if len(cases) != 8 or {c["test"] for c in cases} != EXPECTED_L1:
            issues.append("expected_eight_named_l1_tests_not_executed")
    elif len(cases) < 1368:
        issues.append("regression_suite_smaller_than_consolidation_baseline")
    return {"suite": suite, "counts": counts, "total": len(cases),
            "qualified": not issues, "issues": issues, "dependencies": dependencies,
            "tests": cases, "raw_logs_published": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["l1", "regression"], required=True)
    parser.add_argument("--junit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = summarize(args.suite, args.junit, root / "requirements-test-lock.txt")
    result["candidate_sha"] = os.environ.get("L1_CANDIDATE_SHA")
    result["tested_checkout_sha"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("suite", "total", "counts", "qualified", "issues")}))
    raise SystemExit(0 if result["qualified"] else 1)
