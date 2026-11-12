"""Compare executables of the AskMe port on the long runs: old against new compiler.

Each NAME=EXE is a `pystachy build` of examples/askme/askme_native.py. Every
executable must first produce the same transcript on both workloads; the timed
runs are then interleaved and pinned to one core.

usage: compare.py [--runs N] [--steady TASKSxSTEPS] [--core N] NAME=EXE NAME=EXE...
"""

import argparse
import os
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import workload  # noqa: E402
from bench import Bench, first_difference, port_command  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=int, default=9)
    parser.add_argument("--steady", default="20x100")
    parser.add_argument("--core", type=int, default=2)
    parser.add_argument("executables", nargs="+", metavar="NAME=EXE")
    args = parser.parse_args()
    commands = {}
    for item in args.executables:
        name, _, path = item.partition("=")
        if not path or not os.access(path, os.X_OK):
            raise SystemExit(f"{item}: expected NAME=EXECUTABLE")
        commands[name] = port_command([os.path.abspath(path)])
    tasks, steps = (int(part) for part in args.steady.split("x"))
    work = Path(tempfile.mkdtemp(prefix="askme_compare_"))
    try:
        bench = Bench(work, args.core)
        workloads = {
            "navigation": workload.build(tasks, steps),
            "controller": workload.build_light(tasks, steps),
        }
        names = list(commands)
        for label, scenario in workloads.items():
            expected = bench.run(scenario, commands[names[0]], collect=True)
            for name in names[1:]:
                actual = bench.run(scenario, commands[name], collect=True)
                if actual.digest != expected.digest:
                    difference = first_difference(expected.parts, actual.parts)
                    raise SystemExit(f"{label}: {name} differs from {names[0]} at {difference}")
        print(f"transcripts equal on {', '.join(workloads)}; {args.runs} interleaved runs each")
        print(f"{'workload':12} {'name':16} {'wall ms':>9} {'cpu ms':>9} {'rss MB':>7} {'vs ' + names[0]:>12}")
        for label, scenario in workloads.items():
            samples = {name: [] for name in names}
            for _ in range(args.runs):
                for name in names:
                    samples[name].append(bench.run(scenario, commands[name]))
            base = statistics.median(run.wall for run in samples[names[0]])
            for name in names:
                wall = statistics.median(run.wall for run in samples[name])
                cpu = statistics.median(run.cpu for run in samples[name])
                rss = statistics.median(run.rss_kb for run in samples[name]) / 1024
                print(f"{label:12} {name:16} {wall * 1000:9.0f} {cpu * 1000:9.0f} {rss:7.0f} {base / wall:11.2f}x")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
