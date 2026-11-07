"""Run the binding-index counter/calibration/timing cohorts in one owned slot."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path('/workspace/scratch/5798eb31a437/scope-index')
BASE = Path('/workspace/scratch/5798eb31a437/compiler-work')
PY = '/workspace/scratch/e98dc1e3e6cd/dev/bin/python'
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=False)
os.sched_setaffinity(0, {0})
env = {k: v for k, v in os.environ.items() if not k.startswith('PYSTACHY_')}
env.update(PATH='/workspace/scratch/e98dc1e3e6cd/dev/bin:' + env.get('PATH', ''), PYTHONHASHSEED='0')
report = dict(complete=False, steps=[], affinity=sorted(os.sched_getaffinity(0)),
              load_before=list(os.getloadavg()), measurement_scope='frontend only; no whole-compiler speedup claim',
              baseline_bootstrap='../main/report.json', candidate_bootstrap='../scope-index-bootstrap/report.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compilers():
    # Observations of other sessions, not a claim that the whole host is idle.
    observed = []
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            name = (process/'comm').read_text().strip()
            args = (process/'cmdline').read_bytes().split(b'\0')
            if not (name in ('clang', 'clang-18', 'opt', 'llvm-as', 'llvm-link', 'make', 'pystachy') or
                    name.startswith('python') and any(x.endswith(b'/pystachy.py') or x == b'pystachy.py' for x in args)):
                continue
            status = dict(line.split(':', 1) for line in (process/'status').read_text().splitlines() if ':' in line)
            if status.get('State', '').strip().startswith('Z'):
                continue
            observed.append(dict(pid=int(process.name), executable=name,
                                 state=status.get('State', '').strip(),
                                 allowed_cpus=status.get('Cpus_allowed_list', '').strip()))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return observed


def save():
    (OUT/'cohorts.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


def run(name, options, limit):
    command = [PY, str(ROOT/'bench/exception_bindings/run.py'), '--baseline', str(BASE), '--candidate', str(ROOT),
               '--python', PY, '--cpu', '0', '--output', str(OUT/(name+'.json')), *options]
    item = dict(name=name, command=command, timeout_s=limit, other_compilers_before=compilers())
    report['steps'].append(item)
    save()
    started = time.monotonic()
    child = None
    try:
        with (OUT/(name+'.log')).open('wb') as log:
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            print(f'{name} started with a {limit}s cohort limit', flush=True)
            item['returncode'] = child.wait(timeout=limit)
        if item['returncode']:
            raise RuntimeError(f'{name} failed: {item["returncode"]}')
        result = json.loads((OUT/(name+'.json')).read_text())
        if not result['complete']:
            raise RuntimeError(f'{name} produced an incomplete report')
        return result
    except BaseException as error:
        item['error'] = repr(error)
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
        raise
    finally:
        item['wall_s'] = time.monotonic() - started
        item['log_sha256'] = sha(OUT/(name+'.log'))
        item['other_compilers_after'] = compilers()
        save()
        print(name, item.get('returncode'), round(item['wall_s'], 3), 'seconds', flush=True)


try:
    report['controller_sha256'] = sha(Path(__file__))
    report['host_note'] = 'Team heavy jobs are serialized. Other sessions may run on this shared host; compiler-process observations and host load are recorded, not proof of an otherwise idle host.'
    for label, root, build_dir in (('baseline', BASE, 'main'), ('candidate', ROOT, 'scope-index-bootstrap')):
        evidence = ROOT.parent/'baseline-evidence'/build_dir/'report.json'
        built = json.loads(evidence.read_text())
        if not built['complete'] or not all(sha(root/p) == digest for p, digest in built['sources'].items()):
            raise RuntimeError(f'{label} sources do not match their successful bootstrap')
        if sha(root/'pystachy') != built['artifacts']['pystachy']['sha256']:
            raise RuntimeError(f'{label} binary does not match its successful bootstrap')
        report[label+'_bootstrap_sha256'] = sha(evidence)
    report['cpu'] = [line for line in Path('/proc/cpuinfo').read_text().splitlines()
                     if line.startswith(('vendor_id', 'model name'))][:2]
    report['cgroup'] = {name: (Path('/sys/fs/cgroup')/name).read_text().strip()
                        for name in ('cpu.max', 'memory.max') if (Path('/sys/fs/cgroup')/name).is_file()}
    save()
    run('counts', ['--sizes', '32,64,128', '--rounds', '1', '--counts'], 120)
    native = ['--baseline-native', str(BASE/'pystachy'), '--candidate-native', str(ROOT/'pystachy')]
    calibration = run('calibration', ['--sizes', '500', '--rounds', '1', *native], 180)
    total = sum(sample['wall_s'] for case in calibration['cases'] for sample in case['samples'])
    # Choose sizes using execution cost only, before the repeated timing cohort.
    # A quadratic model for every shape/host is deliberately conservative; the
    # retained estimate is not an observed scaling result.
    sizes = [500, 1000, 2000]
    while 5 * sum((size/500)**2 for size in sizes) * total > 480 and sizes[0] > 64:
        sizes = [size//2 for size in sizes]
    report['selected_sizes'] = sizes
    report['calibration_frontend_wall_s'] = total
    report['projected_timing_wall_s'] = dict(
        linear_model=5 * sum(size/500 for size in sizes) * total,
        quadratic_model=5 * sum((size/500)**2 for size in sizes) * total,
        note='Sizing estimates only; actual scaling and controller overhead can differ')
    save()
    print('timing sizing:', json.dumps(report['projected_timing_wall_s']), 'sizes', sizes, flush=True)
    run('timing', ['--sizes', ','.join(str(size) for size in sizes), '--rounds', '5', *native], 600)
    report['complete'] = True
except BaseException as error:
    report['error'] = repr(error)
    raise
finally:
    report['load_after'] = list(os.getloadavg())
    save()
