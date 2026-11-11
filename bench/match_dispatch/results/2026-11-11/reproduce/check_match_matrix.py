import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
sys.path.insert(0, str(root / 'tools'))
import dynany_optin as optin

cases = sorted(str(p.relative_to(root)) for p in (root / 'tests/programs/language').glob('match_*.py'))
cases += sorted(str(p.relative_to(root)) for p in (root / 'tests/programs/inference').glob('dynany_match*.py'))
cases += ['tests/programs/apps/match_dispatch_workloads.py', 'tests/programs/generators/gen_match_dispatch.py']
configs = [('python-int-gc', [b'# pystachy: python-int\n'], '1'),
           ('dynamic-any-gc', [b'# pystachy: dynamic-any\n'], '1'),
           ('combined', [b'# pystachy: python-int\n', b'# pystachy: dynamic-any\n'], '0'),
           ('combined-gc', [b'# pystachy: python-int\n', b'# pystachy: dynamic-any\n'], '1')]
report = {'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
          'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'compiler_sha256': hashlib.sha256((root/'pystachy').read_bytes()).hexdigest(),
          'cases': cases, 'configurations': []}
for name, pragmas, stress in configs:
    with tempfile.TemporaryDirectory(prefix='match-matrix-') as temporary:
        temp = Path(temporary)
        overlay = temp/'tree'
        optin.prepare_tree(root, overlay, cases, pragmas[0])
        for pragma in pragmas[1:]:
            for case in cases:
                path = overlay/case
                path.write_bytes(optin.opt_in(path.read_bytes(), pragma))
        work = temp/'work'
        work.mkdir()
        env = optin.environment(root, work)
        env.update(PYSTACHY_GC_STRESS_PROGRAM=stress, PYSTACHY_JOBS='2', PYSTACHY_PROGRAM_CACHE='0')
        oracle_status, oracle = optin.run(['sh','tests/record.sh',*cases],overlay,env,120)
        status, output = optin.run(['sh','tests/run.sh',str(root/'pystachy'),'jit aot',*cases],overlay,env,240)
        expected = f'{2*len(cases)} passed, 0 failed'
        passed = (oracle_status == 0 and all('[exit 0]' in row for row in oracle.splitlines())
                  and len(oracle.splitlines()) == len(cases) and status == 0 and expected in output)
        row={'name':name,'stress':stress,'pragmas':[p.decode().strip() for p in pragmas],
             'input_sha256':{case:hashlib.sha256((overlay/case).read_bytes()).hexdigest() for case in cases},
             'oracle_status':oracle_status,'oracle':oracle,'status':status,'output':output,'passed':passed}
        report['configurations'].append(row)
        print(name, 'PASS' if passed else 'FAIL', output.strip(), flush=True)
        (root/'build/match-mode-matrix.json').write_text(json.dumps(report,indent=2)+'\n')
if not all(row['passed'] for row in report['configurations']):
    raise SystemExit(1)
