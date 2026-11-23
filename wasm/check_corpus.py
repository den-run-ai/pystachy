"""Compare the corpus in tests/run.sh's Wasm modes with wasm/known_differences.txt (wasm/README.md).

usage: python3 wasm/check_corpus.py [--compiler CMD] [--modes "wasm wasm-tir"] [--log FILE] [PROGRAM...]

Runs tests/run.sh CMD MODES PROGRAM... (default: ./pystachy, both modes and every
tests/programs/AREA/*.py) and reads its FAIL lines; with --log, reads the report that such a run
already wrote. Exits 1 when a program differs from CPython in a mode that known_differences.txt
does not name for it. Entries whose programs now match are listed, and the exit status stays 0,
so a fix can land before its entry goes. Exits 2 when the list is malformed or names a program the
corpus lacks, or when there is no report.
"""
import argparse
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWN = os.path.join(ROOT, "wasm", "known_differences.txt")
MODES = ("wasm", "wasm-tir")
REASONS = ("errno", "dev-full", "process", "descriptors", "enosys", "signal", "select", "thread",
           "closed-stdio", "gc", "libm", "unexplained")
FAIL = re.compile(r"^FAIL (\S+) \((\S+)\)$")


def known(text: str) -> dict:
    # {(program, mode): reason} of the list's text
    out = {}
    for n, line in enumerate(text.split("\n"), 1):
        words = line.split()
        if not words or line.startswith("#"):
            continue
        if len(words) < 2 or any(m not in MODES for m in words[2:]):
            raise ValueError(f"known_differences.txt:{n}: expected NAME REASON [MODE...]")
        if words[1] not in REASONS and not re.fullmatch(r"#[1-9][0-9]*", words[1]):
            raise ValueError(f"known_differences.txt:{n}: unknown reason {words[1]}")
        for mode in words[2:] or MODES:
            if (words[0], mode) in out:
                raise ValueError(f"known_differences.txt:{n}: {words[0]} ({mode}) is listed twice")
            out[(words[0], mode)] = words[1]
    return out


def failures(report: str) -> set:
    # the (program, mode) pairs that a tests/run.sh report names as failed
    return {(m[1], m[2]) for m in map(FAIL.match, report.split("\n")) if m}


def compare(expected: dict, failed: set, names: set, modes: list) -> tuple:
    # (failures the list lacks, entries of the programs and modes run that no longer fail)
    unexpected = sorted(f for f in failed if f not in expected)
    fixed = sorted(k for k in expected if k[0] in names and k[1] in modes and k not in failed)
    return unexpected, fixed


def corpus() -> list:
    return sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "tests", "programs", "*", "*.py")))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--compiler", default="./pystachy")
    ap.add_argument("--modes", default=" ".join(MODES))
    ap.add_argument("--log", help="a tests/run.sh report of these programs and modes")
    ap.add_argument("programs", nargs="*")
    args = ap.parse_args()
    modes = args.modes.split()
    if not modes or any(m not in MODES for m in modes):
        ap.error(f"--modes takes {' and '.join(MODES)}")
    programs = args.programs or corpus()
    try:
        expected = known(open(KNOWN, encoding="utf-8").read())
    except ValueError as e:
        print(f"check_corpus: {e}", file=sys.stderr)
        return 2
    everything = {os.path.basename(p)[:-3] for p in corpus()}
    missing = sorted({k[0] for k in expected} - everything)
    if missing:
        print(f"check_corpus: known_differences.txt names programs the corpus lacks: {' '.join(missing)}", file=sys.stderr)
        return 2
    if args.log:
        report = open(args.log, encoding="utf-8", errors="replace").read()
    else:
        run = subprocess.run(["sh", "tests/run.sh", args.compiler, " ".join(modes)] + programs, cwd=ROOT,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        report = run.stdout
        sys.stdout.write(report)
    if not re.search(r"^selected \d+ cases$", report, re.MULTILINE):
        print("check_corpus: no tests/run.sh report", file=sys.stderr)
        return 2
    names = {os.path.basename(p)[:-3] for p in programs}
    unexpected, fixed = compare(expected, failures(report), names, modes)
    for name, mode in fixed:
        print(f"now matches CPython: {name} ({mode}); remove its entry from wasm/known_differences.txt")
    for name, mode in unexpected:
        print(f"unexpected difference: {name} ({mode})")
    print(f"check_corpus: {len(unexpected)} unexpected, {len(fixed)} listed now match")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
