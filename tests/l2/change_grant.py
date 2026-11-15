"""Independent trusted-operator process used to race CAS, never an HTTP API."""
import os
from pathlib import Path
import sys
import time
from rkjo_kernel.security.authority import PostgreSQLSecurityAuthority, AuthorityConflict, api_claim

barrier = Path(sys.argv[1])
deadline = time.monotonic()+10
while not barrier.exists():
    if time.monotonic() > deadline: raise TimeoutError('Grant barrier not released')
    time.sleep(.01)
try:
    PostgreSQLSecurityAuthority(os.environ['RKJO_SECURITY_AUTHORITY_DATABASE_URL']).change(
        api_claim('tenant-a','alice','operator'), enabled=False, expected_version=1, actor='concurrent-test-operator')
    print('changed')
except AuthorityConflict:
    print('conflict')
