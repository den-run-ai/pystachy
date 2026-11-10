"""Count C-runtime allocation requests separately from ordinary timing runs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--changed', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--llvm', type=Path, required=True)
    parser.add_argument('--reuse-binaries', action='store_true')
    args = parser.parse_args()
    base, changed, work = (p.resolve() for p in (args.base, args.changed, args.workdir))
    expected = json.loads((work / 'results.json').read_text())['oracles']
    prior = json.loads((work / 'allocations.json').read_text()) if args.reuse_binaries else {}
    rootenv = {k: v for k, v in os.environ.items()
               if not k.startswith('PYSTACHY_') and k not in ('PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD', 'ASAN_OPTIONS')}
    output = {'scope': 'C runtime allocation requests; not total physical traffic or retained memory',
              'instrumentation': '-DPYSTACHY_PROFILE_DATA; counted binaries excluded from timing results',
              'samples': []}
    cases = [
        ('direct', 'micro', ['direct', '30000']),
        ('ranks', 'micro', ['ranks', '30000']),
        ('bpe', 'bpe', [str(work / 'sources/frankenstein_intro.txt'), '1024', '100', '100']),
    ]
    for name, root in [('main', base), ('changed', changed)]:
        env = dict(rootenv, PYSTACHY_HOME=str(root), PYSTACHY_LLVM=str(args.llvm.resolve()),
                   PYSTACHY_CFLAGS='-DPYSTACHY_PROFILE_DATA', PYSTACHY_IRCHECK='1',
                   PYSTACHY_CACHE=str(work / ('profile-cache-' + name)),
                   PYSTACHY_PATH=str(work / 'sources'), PYTHONHASHSEED='0')
        for workload, source in [('micro', base / 'bench/optional_scalars.py'),
                                 ('bpe', work / 'driver/stages.py')]:
            binary = work / ('profile-' + name + '-' + workload)
            command = [sys.executable, str(root / 'pystachy.py'), 'build', str(source), '-o', str(binary)]
            if args.reuse_binaries:
                hashes = {sample['binary_sha256'] for sample in prior['samples']
                          if sample['variant'] == name and ('bpe' if sample['workload'] == 'bpe' else 'micro') == workload}
                if hashes != {digest(binary)}:
                    raise RuntimeError(('profile binary changed', binary))
            else:
                build = subprocess.run(command, env=env, cwd=root, capture_output=True, text=True, timeout=180)
                if build.returncode or build.stdout or build.stderr:
                    raise RuntimeError((command, build.returncode, build.stdout, build.stderr))
            for mode, matching, params in cases:
                if matching != workload:
                    continue
                # The runtime copies argv[0]. Keep it identical so binary-name
                # length cannot produce a spurious allocation-byte difference.
                run = subprocess.run(['optional-lookup-profile', *params], executable=str(binary), env=rootenv,
                                     capture_output=True, text=True, timeout=120)
                actual = hashlib.sha256(run.stdout.encode()).hexdigest()
                if run.returncode or actual != expected[mode]['stdout_sha256']:
                    raise RuntimeError((name, mode, run.returncode, run.stdout, run.stderr))
                records = [line.removeprefix('pystachy-data: ') for line in run.stderr.splitlines()
                           if line.startswith('pystachy-data: ')]
                if len(records) != 1:
                    raise RuntimeError(('missing allocation record', run.stderr))
                counters = json.loads(records[0])
                record = {'variant': name, 'workload': mode, 'executable': str(binary),
                          'command': ['optional-lookup-profile', *params],
                          'binary_sha256': digest(binary), 'stdout_sha256': actual, 'counters': counters}
                output['samples'].append(record)
                (work / 'allocations.json').write_text(json.dumps(output, indent=2) + '\n')
                print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
