"""bench: csvstat.py under CPython and as a Pystachy AOT executable, on a generated file of 200,000
orders (the median wall time of N runs, with process start-up, and the peak RSS of one); and
rwbench.py, csv.reader's and csv.writer's own time per row on that file (the medians of N runs).
CPython's and the executable's runs are taken in turn, after an untimed one of each.

usage: python3 -I bench.py PYSTACHY [N]
The file and the executables go to build/csvstat/ of the checkout.
"""
import hashlib
import os
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from example_bench import measure_pair, parse_timings, positive_int, run


def rwbench_timings(output: bytes, rows: int) -> dict[str, float]:
    lines = output.decode().splitlines()
    if len(lines) != 2 or lines[0] != f"{rows} rows, read back as written":
        raise ValueError(f"invalid CSV round-trip report: {output!r}")
    return parse_timings(lines[1], ("read", "parse", "write"), unit="us/row")


def per_row(commands: list[list[str]], runs: int, rows: int, copy: Path) -> list[list[float]]:
    runs = positive_int(runs)
    rows = positive_int(rows, "rows")
    if not commands:
        raise ValueError("expected at least a CPython command")

    def sample(cmd, expected=None):
        # A failed write must not pass by leaving a previous run's copy in place.
        copy.unlink(missing_ok=True)
        result = run(cmd)
        timings = rwbench_timings(result.stdout, rows)
        with copy.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if expected is not None and digest != expected:
            raise ValueError(f"CSV copy differs for {cmd!r}")
        return timings, digest

    # CPython establishes both the row report and the written bytes before timing.
    _, expected = sample(commands[0])
    for cmd in commands[1:]:
        sample(cmd, expected)
    times = [{label: [] for label in ("read", "parse", "write")} for _ in commands]
    for repeat in range(runs):
        order = range(len(commands)) if repeat % 2 == 0 else range(len(commands) - 1, -1, -1)
        for index in order:
            timings, _ = sample(commands[index], expected)
            for label, value in timings.items():
                times[index][label].append(value)
    return [[statistics.median(values) for values in sample.values()] for sample in times]


def main() -> None:
    pys = sys.argv[1]
    runs = positive_int(sys.argv[2]) if len(sys.argv) > 2 else 5
    rows = 200000
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "..", "build", "csvstat")
    os.makedirs(out, exist_ok=True)
    data = os.path.join(out, f"orders_{rows}.csv")
    if not os.path.exists(data):
        # (into a file of its own first: an interrupted run leaves no short file under this name)
        with open(data + ".part", "w") as f:
            run([sys.executable, "-I", os.path.join(here, "gencsv.py"), str(rows)], stdout=f)
        os.replace(data + ".part", data)
    print(f"{data}: {rows} rows, {os.path.getsize(data) / 1e6:.1f} MB")
    exes = {}
    for prog in ["csvstat", "rwbench"]:
        exes[prog] = os.path.join(out, prog + "_aot")
        t = time.perf_counter()
        run([pys, "build", os.path.join(here, prog + ".py"), "-o", exes[prog]])
        print(f"pystachy build {prog}.py: {time.perf_counter() - t:.2f} s")

    csvstat = os.path.join(here, "csvstat.py")
    print(f"{'csvstat':10} {'CPython':>9} {'AOT':>9} {'speedup':>8} {'CPython RSS':>12} {'AOT RSS':>9}")
    for extra in [[], ["--csv"]]:
        c, a = measure_pair([[sys.executable, "-I", csvstat, data] + extra, [exes["csvstat"], data] + extra], runs)
        print(f"{' '.join(extra) or 'report':10} {c.wall_s:8.3f}s {a.wall_s:8.3f}s {c.wall_s / a.wall_s:7.1f}x {c.rss_kib / 1024:9.1f} MB {a.rss_kib / 1024:6.1f} MB")
    copy = os.path.join(out, "copy.csv")
    c, a = per_row([[sys.executable, "-I", os.path.join(here, "rwbench.py"), data, copy], [exes["rwbench"], data, copy]], runs, rows + 1, Path(copy))
    print(f"{'per row':10} {'CPython':>9} {'AOT':>9} {'speedup':>8}")
    for k, what in enumerate(["read", "parse", "write"]):
        print(f"{what:10} {c[k]:7.3f}us {a[k]:7.3f}us {c[k] / a[k]:7.1f}x")


if __name__ == "__main__":
    main()
