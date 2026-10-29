#!/usr/bin/env python3
"""Write tests/case_weights.txt, the weights that balance the corpus's shards (tests/corpus.sh's
corpus_shard, which tests/verify.sh's shard_cases and tools/shard_cases.sh use).

Each TIMES file holds "MILLISECONDS CASE" lines, as tests/run.sh appends them with PYSTACHY_CASE_TIMES
(tests/verify.sh keeps its suite steps' as build/verify/*-times.log, in each CI group's artifact).
Every file's times are divided by the median time of the corpus programs in it (it must time at
least MIN_PROGRAMS of them), so that files from runners of different speeds and from shards of
different mixes agree; a case timed more than once gets the median of its scaled times. A weight is
a case's time in thousandths of a median program's, at least 1. Give it the times of one
configuration (tests-native's are the reference: JIT and AOT, the stage-2 compiler).

The table lists the corpus's timed cases in C order, after a "default program W" and a "default
rejection W" line: the median weights of the programs (deviations included) and of the rejections,
which corpus_shard gives a case the table lacks. With --keep, a case no file timed keeps its weight
from the existing table. Cases outside the corpus are left out. Whatever the table holds, every case
of the corpus runs in exactly one shard: the weights decide which, never whether.

usage: python3 tools/case_weights.py [--keep] [-o tests/case_weights.txt] TIMES...
"""
import argparse
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
TABLE = "tests/case_weights.txt"
MIN_PROGRAMS = 20
MAX_WEIGHT = 999_999_999  # (corpus_shard ignores a weight of more than nine digits)
HEADER = ("# Weights of the corpus's cases, which balance its shards (tests/corpus.sh's corpus_shard):\n"
          "# a case's time in thousandths of a median program's. Written by tools/case_weights.py from\n"
          "# tests/run.sh's PYSTACHY_CASE_TIMES; a stale or missing entry costs balance, never coverage.\n")


def corpus(root=ROOT):
    """The cases of tests/corpus.sh's corpus, in C order."""
    cases = [*root.glob("tests/programs/*/*.py"), *root.glob("tests/deviations/*.py"),
             *root.glob("tests/errors/*/*.py")]
    return sorted((p.relative_to(root).as_posix() for p in cases if p.is_file()), key=lambda c: c.encode())


def kind(case):
    return "rejection" if case.startswith("tests/errors/") else "program"


def read_times(path):
    """The (case, milliseconds) pairs of a PYSTACHY_CASE_TIMES file; a malformed line is an error."""
    pairs = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        fields = line.split(" ", 1)
        if len(fields) != 2 or not fields[0].isdigit() or not fields[0].isascii() or not fields[1]:
            raise ValueError(f"{path}:{number}: expected MILLISECONDS CASE, got {line!r}")
        pairs.append((fields[1], int(fields[0])))
    return pairs


def read_table(path):
    """The weights and defaults of an existing table, read as corpus_shard reads them."""
    weights, defaults = {}, {}
    if not Path(path).is_file():
        return weights, defaults
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        valid = [f.isascii() and f.isdigit() and len(f) <= 9 for f in fields]
        if len(fields) == 3 and fields[0] == "default" and fields[1] in ("program", "rejection") and valid[2]:
            defaults[fields[1]] = int(fields[2])
        elif len(fields) == 2 and valid[0]:
            weights[fields[1]] = int(fields[0])
    return weights, defaults


def weigh(files, cases, kept=None):
    """Each timed case's weight: its median time, each file's scaled to its median program's."""
    known = set(cases)
    scaled = {}
    for path in files:
        pairs = [(case, ms) for case, ms in read_times(path) if case in known]
        programs = [ms for case, ms in pairs if case.startswith("tests/programs/")]
        if len(programs) < MIN_PROGRAMS:
            raise ValueError(f"{path}: times {len(programs)} corpus programs, fewer than {MIN_PROGRAMS}: "
                             "too few to scale its times by their median")
        median = statistics.median(programs)
        if median <= 0:
            raise ValueError(f"{path}: its programs' median time is 0 ms")
        for case, ms in pairs:
            scaled.setdefault(case, []).append(ms * 1000 / median)
    weights = {case: min(MAX_WEIGHT, max(1, round(statistics.median(values)))) for case, values in scaled.items()}
    for case, weight in (kept or {}).items():
        if case in known and case not in weights:
            weights[case] = weight
    return weights


def table(weights):
    """The table's text: the defaults, then each case's weight in C order."""
    lines = [HEADER]
    for name in ("program", "rejection"):
        values = [w for case, w in weights.items() if kind(case) == name]
        lines.append(f"default {name} {round(statistics.median(values)) if values else 1000}\n")
    lines += [f"{weights[case]} {case}\n" for case in sorted(weights, key=lambda c: c.encode())]
    return "".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("times", nargs="+", type=Path, help="tests/run.sh PYSTACHY_CASE_TIMES files")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / TABLE)
    parser.add_argument("--keep", action="store_true", help="keep the existing weights of cases not timed")
    args = parser.parse_args(argv)
    cases = corpus()
    try:
        kept = read_table(args.output)[0] if args.keep else None
        weights = weigh(args.times, cases, kept)
    except (OSError, ValueError) as error:
        print(f"tools/case_weights.py: {error}", file=sys.stderr)
        return 1
    args.output.write_text(table(weights))
    print(f"{args.output}: {len(weights)} of {len(cases)} cases weighed; "
          f"the rest weigh their kind's default")
    return 0


if __name__ == "__main__":
    sys.exit(main())
