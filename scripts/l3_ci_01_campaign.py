"""Fixed ten independent cold starts; never retry a failing test or overwrite evidence."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--campaign',required=True,choices=['initial','corrected'])
    parser.add_argument('--tag',required=True)
    args=parser.parse_args()
    assert args.tag.isalnum(), 'Use an alphanumeric unique campaign tag.'
    directory=ROOT/'.test-results'/f'l3-ci-01-{args.campaign}-{args.tag}'
    directory.mkdir(parents=True,exist_ok=False)
    lock={}
    for line in (ROOT/'requirements-test-lock.txt').read_text().splitlines():
        if '==' in line and not line.startswith('#'):
            name,pinned=line.split('==')
            assert version(name)==pinned,(name,pinned,version(name))
            lock[name]=pinned
    protocol=ROOT/'docs/audit/L3_CI_01_PROTOCOL.md'
    metadata={'repetitions':10,'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
              'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'lock':lock,'results':[]}
    (directory/'results.json').write_text(json.dumps(metadata,indent=2))
    for i in range(1,11):
        project=f'rkjo-l1-l3ci-{args.tag}-{args.campaign}-{i:02}'
        for kind in ('container','volume'):
            existing=subprocess.check_output(['docker',kind,'ls','-q','--filter',f'label=com.docker.compose.project={project}'],text=True)
            assert not existing.strip(),f'Project already exists: {project}'
        compose=['docker','compose','-p',project,'-f',str(ROOT/'compose.l1.yml')]
        output=directory/f'{i:02}-compose.stdout'
        with output.open('w') as log:
            started=subprocess.run(compose+['up','-d','--wait'],stdout=log,stderr=subprocess.STDOUT).returncode
            case={'index':i,'project':project,'infrastructure_exit':started}
            try:
                if started==0:
                    command=[sys.executable,str(ROOT/'scripts/l1_test.py'),'--project',project,
                             '--evidence-dir',str(directory/f'{i:02}-raw'),
                             'tests/l1/test_acceptance.py::test_two_steps_restart_and_insert_only','-q']
                    case['exit_code']=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
                    junit=directory/f'{i:02}-raw/acceptance.xml'
                    if junit.exists():
                        tests=list(ET.parse(junit).iter('testcase'))
                        case['tests']=[{'name':t.attrib['name'],'outcomes':[c.tag for c in t if c.tag in ('error','failure','skipped')]} for t in tests]
                        case['passed']=case['exit_code']==0 and len(tests)==1 and not case['tests'][0]['outcomes']
                else:
                    case['passed']=False
            finally:
                subprocess.run(compose+['down'],stdout=log,stderr=subprocess.STDOUT,check=True)
                metadata['results'].append(case)
                (directory/'results.json').write_text(json.dumps(metadata,indent=2))
                print(json.dumps(case),flush=True)
    return 0 if all(r.get('passed') for r in metadata['results']) else 1


if __name__=='__main__':
    raise SystemExit(main())
