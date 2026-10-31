"""New paired normal-driver measurements; archived series stays historical."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OLD = Path('/workspace/scratch/e858f72517b9')
OUT = ROOT / 'object-current'
HOMES = {'main': OLD / 'baselines/main', 'da84': OLD / 'pystachy'}
EXPECTED = {
    'main': ('06e3ad5d08514ba31fb231fe4636a962fe6578e3', '14571111190e9c2efdf5d7e5620e498cb6697f05ef97e4a05953b240160c9e51'),
    'da84': ('da84d382ff83f09e46d4ef104e62e6f64e9c37c1', '8ee9b55b99c85a1406198643a5405d6e58ef566ec5896f6af3b03daf478b3f75'),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs(home):
    paths = [home / f for f in ('pystachy.py', 'runtime.c', 'runtime.py', 'pyext.c', 'pyembed.c')]
    for folder in ('src', 'lib', 'mpz', 'ryu'):
        paths += [p for p in (home / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.c', '.h')]
    return {str(p.relative_to(home)): digest(p) for p in sorted(paths)}


def execute(argv, env, cwd=ROOT, timeout=120):
    started = time.perf_counter()
    p = subprocess.run(list(map(str, argv)), env=env, cwd=cwd,
                       capture_output=True, text=True, timeout=timeout)
    record = dict(argv=list(map(str, argv)), returncode=p.returncode,
                  stdout=p.stdout, stderr=p.stderr,
                  process_wall_s=time.perf_counter() - started)
    if p.returncode:
        raise RuntimeError(record)
    return record


def parse(record, expected=None):
    lines = record['stdout'].splitlines()
    label, value = lines[0].split()
    value = int(value)
    assert label == 'warm' and len(lines) == 8
    rows = [list(map(int, line.split())) for line in lines[1:]]
    assert all(len(row) == 2 and row[0] == value and row[1] > 0 for row in rows)
    assert expected is None or value == expected
    return dict(record, checksum=value, kernel_ns=[r[1] for r in rows],
                median_kernel_ns=statistics.median(r[1] for r in rows))


def main():
    OUT.mkdir(exist_ok=False)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('PYSTACHY_') and k not in ('PYTHONPATH', 'PYTHONHOME')}
    env.update(PYSTACHY_LLVM=os.environ['PYSTACHY_LLVM'], PYTHONHASHSEED='0')
    source = HOMES['da84'] / 'bench/recursion/object_calls.py'
    report = dict(status='incomplete', purpose=__doc__, platform=platform.platform(),
                  cpu=Path('/proc/cpuinfo').read_text(), cpu_affinity=[0],
                  source=str(source), source_sha256=digest(source),
                  runner_sha256=digest(__file__), variants={}, results={})

    def save():
        p = OUT / 'report.json'
        temp = p.with_suffix('.tmp')
        temp.write_text(json.dumps(report, indent=2) + '\n')
        temp.replace(p)

    envs = {}
    os.sched_setaffinity(0, {0})
    try:
        for name, home in HOMES.items():
            cache = OUT / (name + '-cache')
            old_cache = OLD / 'perf-work/results-final-da84' / ('main-cache' if name == 'main' else 'candidate-cache')
            if old_cache.exists():
                shutil.copytree(old_cache, cache)
            else:
                cache.mkdir()
            envs[name] = dict(env, PYSTACHY_HOME=str(home), PYSTACHY_CACHE=str(cache))
            report['variants'][name] = dict(
                commit=execute(['git', 'rev-parse', 'HEAD'], env, home)['stdout'].strip(),
                tree=execute(['git', 'rev-parse', 'HEAD^{tree}'], env, home)['stdout'].strip(),
                compiler=str(home / 'pystachy'), compiler_sha256=digest(home / 'pystachy'),
                input_sha256=inputs(home),
                cache_source=str(old_cache) if old_cache.exists() else None)
            assert (report['variants'][name]['commit'], report['variants'][name]['compiler_sha256']) == EXPECTED[name]
            assert not execute(['git', 'status', '--porcelain=v1'], env, home)['stdout']
        save()
        for n in (100000, 1000000):
            oracle = parse(execute([sys.executable, source, n], env))
            row = dict(n=n, cpython=oracle, warmups={}, rounds=[], load_start=os.getloadavg())
            report['results'][str(n)] = row
            save()
            for name, home in HOMES.items():
                row['warmups'][name] = parse(execute([home / 'pystachy', 'run', source, n], envs[name]), oracle['checksum'])
                save()
            for repeat in range(10):
                order = ['main', 'da84'] if repeat % 2 == 0 else ['da84', 'main']
                result = dict(order=order, observations={})
                row['rounds'].append(result)
                for name in order:
                    result['observations'][name] = parse(execute(
                        [HOMES[name] / 'pystachy', 'run', source, n], envs[name]), oracle['checksum'])
                    save()
                print('object', n, repeat, {name: value['median_kernel_ns'] for name, value in result['observations'].items()}, flush=True)
            medians = {name: [r['observations'][name]['median_kernel_ns'] for r in row['rounds']] for name in HOMES}
            ratios = [r['observations']['da84']['median_kernel_ns'] / r['observations']['main']['median_kernel_ns'] for r in row['rounds']]
            row['summary'] = dict(median_of_process_medians_ns={name: statistics.median(values) for name, values in medians.items()},
                                  paired_ratios=ratios, median_paired_ratio=statistics.median(ratios),
                                  slower_pairs=sum(r > 1 for r in ratios), load_end=os.getloadavg())
            print('summary', n, row['summary'], flush=True)
            save()
        for name, home in HOMES.items():
            assert digest(home / 'pystachy') == report['variants'][name]['compiler_sha256']
            assert inputs(home) == report['variants'][name]['input_sha256']
        assert digest(source) == report['source_sha256']
        report['status'] = 'complete'
    except BaseException as error:
        report.update(status='error', error=repr(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
