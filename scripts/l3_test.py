"""Explicit L3 real-provider recipe; no model install, .env or shared DB/broker."""
from datetime import datetime, timezone
from uuid import uuid4
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import httpx
import psycopg
from l1_test import ROOT, environment

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--ollama-url', default='http://127.0.0.1:11434')
    parser.add_argument('--model', default='qwen3:8b')
    parser.add_argument('--expected-digest', default='500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41')
    args, extra = parser.parse_known_args()
    if not args.project.startswith('rkjo-l1-l3-'):
        raise ValueError('A dedicated rkjo-l1-l3-* project is required.')
    from urllib.parse import urlparse
    parsed = urlparse(args.ollama_url)
    if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.scheme != 'http':
        raise ValueError('Recipe provider must be local HTTP Ollama.')
    env = environment(args.project)
    env.update(RKJO_SECURITY_PROFILE='distributed',
               RKJO_SECURITY_AUTHORITY_DATABASE_URL=env['RKJO_DATABASE_URL'],
               RKJO_L1_EVIDENCE=str(ROOT / '.test-results/l3' / ('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8])),
               RKJO_LLM_PROVIDER='ollama', RKJO_LLM_MODEL=args.model,
               RKJO_OLLAMA_BASE_URL=args.ollama_url, RKJO_LLM_LOCAL_ONLY='true',
               RKJO_LLM_TIMEOUT_SECONDS='60', RKJO_LLM_MAX_OUTPUT_TOKENS='256',
               RKJO_LLM_MAX_TOTAL_TOKENS='65536', RKJO_LLM_MAX_INPUT_TOKENS='32768',
               RKJO_EMBEDDING_PROVIDER='deterministic', RKJO_EMBEDDING_DIMENSIONS='16',
               RKJO_RETRIEVAL_MODE='hybrid', RKJO_RERANKER='lexical',
               RKJO_RERANKING_MIN_SCORE='0.2', RKJO_RERANKING_MIN_RESULTS='0')
    before = datetime.now(timezone.utc)
    with psycopg.connect(env['RKJO_DATABASE_URL']) as con:
        sql_time = con.execute('SELECT clock_timestamp()').fetchone()[0]
    after = datetime.now(timezone.utc)
    skew = min(abs((sql_time-before).total_seconds()), abs((sql_time-after).total_seconds()))
    if skew > 0.5:
        raise RuntimeError(f'Dedicated PostgreSQL/process clocks differ by {skew:.3f}s; synchronize test infrastructure before running, no retry performed.')
    tags = httpx.get(args.ollama_url + '/api/tags', timeout=5).raise_for_status().json()
    model = next((m for m in tags['models'] if m['name'] == args.model), None)
    if model is None:
        raise RuntimeError('Required existing Ollama model is unavailable; no automatic pull.')
    if model['digest'] != args.expected_digest:
        raise RuntimeError('Existing model digest differs from qualified configuration.')
    evidence = Path(env['RKJO_L1_EVIDENCE'])
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence/'preflight.json').write_text(json.dumps({
        'clock_skew_seconds':skew, 'recorded_at':datetime.now(timezone.utc).isoformat(), 'project':args.project, 'provider':'ollama', 'model':args.model, 'digest':model['digest'],
        'corpus_sha256':hashlib.sha256((ROOT/'tests/l3/corpus.json').read_bytes()).hexdigest(),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    }, indent=2))
    (ROOT/'.test-results/l3/last-run.json').write_text(json.dumps({'directory':str(evidence.relative_to(ROOT))}))
    print(json.dumps({'l3_evidence_directory':str(evidence.relative_to(ROOT))}), flush=True)
    raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest'] +
                    (extra or ['tests/l3', '-q', '--junitxml=.test-results/l3-acceptance.xml']), cwd=ROOT, env=env))
