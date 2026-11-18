"""L2 reuses the isolated L1 infrastructure/runner, with its own project and evidence."""
import argparse
import json
import time
import httpx
import os
from pathlib import Path
import subprocess
import sys
from l1_test import environment, ROOT

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--oidc-project", required=True)
    args, pytest_args = parser.parse_known_args()
    if not args.project.startswith("rkjo-l1-l2-"):
        raise ValueError("Reserve a dedicated rkjo-l1-l2-* Compose project.")
    env = environment(args.project)
    env.update(RKJO_SECURITY_PROFILE="distributed",
               RKJO_SECURITY_AUTHORITY_DATABASE_URL=env["RKJO_DATABASE_URL"],
               RKJO_L1_EVIDENCE=str(ROOT / ".test-results/l2"))
    if not args.oidc_project.startswith("rkjo-l2-oidc-"):
        raise ValueError("Reserve a dedicated rkjo-l2-oidc-* IdP project.")
    output = subprocess.check_output(["docker", "compose", "-p", args.oidc_project,
        "-f", str(ROOT/"compose.l2-oidc.yml"), "ps", "--format", "json"],text=True)
    decoded = [json.loads(line) for line in output.splitlines() if line.strip()]
    rows = decoded[0] if len(decoded)==1 and isinstance(decoded[0],list) else decoded
    if len(rows)!=1 or rows[0]["Project"]!=args.oidc_project or rows[0]["Service"]!="keycloak":
        raise ValueError("Dedicated Keycloak project required.")
    ports = [p["PublishedPort"] for p in rows[0]["Publishers"]
             if p.get("TargetPort")==8080 and p.get("URL")=="127.0.0.1" and p.get("PublishedPort",0)>0]
    if len(ports)!=1: raise ValueError("Dedicated localhost IdP publisher required.")
    issuer = f"http://127.0.0.1:{ports[0]}/realms/rkjo-l2"
    deadline = time.monotonic()+120
    while True:
        try:
            response = httpx.get(issuer+"/.well-known/openid-configuration",timeout=2)
            if response.status_code==200 and response.json()["issuer"]==issuer: break
        except httpx.TransportError: pass
        if time.monotonic()>deadline: raise TimeoutError("Real test IdP unavailable.")
        time.sleep(.5)
    env.update(RKJO_OIDC_ISSUER=issuer,RKJO_OIDC_AUDIENCE="rkjo-l2-api",
               RKJO_OIDC_JWKS_URL=issuer+"/protocol/openid-connect/certs",
               RKJO_OIDC_TENANT_CLAIM="organization",
               RKJO_OIDC_TENANT_MAP='{"external-a":"tenant-a","external-b":"tenant-b"}')
    Path(env["RKJO_L1_EVIDENCE"]).mkdir(parents=True, exist_ok=True)
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest"] +
        (pytest_args or ["tests/l2", "-q"]), cwd=ROOT, env=env))
