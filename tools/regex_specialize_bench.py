"""Rotate reproducible measurements of the fixed-date regex component probe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import statistics
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CPYTHON = """
import sys, time
sys.path.insert(0, sys.argv[1])
import regex_specialized as bench
repeats = int(sys.argv[2])
def run():
    checksum = 0
    for _ in range(repeats):
        for string in bench.CORPUS:
            for year, month, day in bench.DATE.findall(string):
                checksum += int(year) + int(month) + int(day)
    return checksum
start = time.process_time()
checksum = run()
print('cpython', checksum, time.process_time() - start)
"""


def command(args: list[str]) -> str:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True,
                          check=True).stdout.strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--compiler', help='Optional compiler command; build the probe once first.')
    parser.add_argument('--rounds', type=int, default=7)
    parser.add_argument('--repeats', type=int, default=20000)
    parser.add_argument('--cpu', type=int, help='CPU affinity; defaults to the first available CPU.')
    parser.add_argument('--llvm', type=Path, help='LLVM binary directory for version metadata.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.rounds < 1 or args.repeats < 1:
        parser.error('rounds and repeats must be positive')
    cpu = args.cpu
    available = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else []
    if available:
        cpu = available[0] if cpu is None else cpu
        if cpu not in available:
            parser.error('selected CPU is outside the available affinity mask')
        os.sched_setaffinity(0, {cpu})
    elif cpu is not None:
        parser.error('CPU affinity is unavailable on this host')
    executable = args.executable.resolve()
    if args.compiler:
        executable.parent.mkdir(parents=True, exist_ok=True)
        command(shlex.split(args.compiler) + ['build', 'bench/regex_specialized.py', '-o', str(executable)])
    modes = ['vm', 'generic', 'specialized', 'concrete', 'cpython']
    samples = []
    expected = None
    for round_index in range(args.rounds):
        offset = round_index % len(modes)
        order = modes[offset:] + modes[:offset]
        for index, mode in enumerate(order):
            argv = ([sys.executable, '-c', CPYTHON, str(ROOT / 'bench'), str(args.repeats)]
                    if mode == 'cpython' else [str(executable), mode, str(args.repeats)])
            result = command(argv).splitlines()[-1].split()
            if len(result) != 3 or result[0] != mode:
                raise RuntimeError(f'unexpected {mode} result: {result!r}')
            checksum, seconds = int(result[1]), float(result[2])
            expected = checksum if expected is None else expected
            if checksum != expected or seconds < 0:
                raise RuntimeError(f'{mode} checksum/time mismatch: {checksum}, {seconds}')
            samples.append(dict(round=round_index, order=index, mode=mode,
                                checksum=checksum, cpu_seconds=seconds))
    summaries = {}
    for mode in modes:
        times = [sample['cpu_seconds'] for sample in samples if sample['mode'] == mode]
        summaries[mode] = dict(median=statistics.median(times), minimum=min(times), maximum=max(times))
    source_paths = ['tools/regex_specialize.py', 'bench/regex_date_generated.py',
                    'bench/regex_specialized.py', 'tools/regex_specialize_bench.py',
                    'lib/re/__init__.py', 'lib/re/_sre.py']
    llvm = args.llvm or (Path(os.environ['PYSTACHY_LLVM']) if 'PYSTACHY_LLVM' in os.environ else None)
    metadata = dict(python=sys.version, interpreter=sys.executable, cpu=cpu,
                    available_cpus=available, base_commit=command(['git', 'rev-parse', 'HEAD']),
                    executable=str(executable), executable_sha256=digest(executable),
                    source_sha256={path: digest(ROOT / path) for path in source_paths})
    if llvm is not None:
        metadata['llvm'] = command([str(llvm / 'opt'), '--version']).splitlines()[0]
    report = dict(scope='fixed-date regex extraction component probe', metadata=metadata,
                  rounds=args.rounds, repeats=args.repeats, checksum=expected,
                  samples=samples, summaries=summaries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    for mode, summary in summaries.items():
        print(mode, f"{summary['median']:.6f}s", f"[{summary['minimum']:.6f}, {summary['maximum']:.6f}]")
    print(args.output)


if __name__ == '__main__':
    main()
