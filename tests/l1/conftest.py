"""Preserve full pytest phase/exception without locals before ephemeral CI disappears."""
import json
import os
from pathlib import Path
import re
import traceback
import pytest
from scripts.l1_diagnostics import timestamp


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    directory = Path(os.environ['RKJO_L1_EVIDENCE'])/'pytest-phases'
    directory.mkdir(parents=True,exist_ok=True)
    value = {'nodeid': item.nodeid, 'phase': report.when, 'outcome': report.outcome,
             'time': timestamp(), 'duration': report.duration,
             'exception_type': call.excinfo.typename if call.excinfo else None,
             'exception': ''.join(traceback.format_exception(call.excinfo.type,call.excinfo.value,call.excinfo.tb)) if call.excinfo else None}
    filename = re.sub(r'[^a-zA-Z0-9_.-]','_',item.nodeid)+'-'+report.when+'.json'
    (directory/filename).write_text(json.dumps(value,indent=2))
