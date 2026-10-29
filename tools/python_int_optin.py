"""Run the differential program corpus with its entry modules opted in to promoting ints.

Each selected tests/programs case gets '# pystachy: python-int' as tools/dynany_optin.py gives its
pragma: the same overlay tree, a fresh pinned-CPython oracle for the changed source and the
tests/run.sh JIT/AOT contract, with the baseline rerun on a failure. Promoting ints do not cover
the whole language yet (docs/python-int.md), so many cases fail and no manifest exempts them:
the report records every case and mode, and --compare BASE fails (exit 1) where a check that
passes in an earlier report BASE no longer does, listing the newly passing ones too. A change to
promoting ints is checked against a report of its base's compiler (docs/testing.md).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shlex
import signal
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dynany_optin as optin

ROOT = optin.ROOT
PRAGMA = b"# pystachy: python-int\n"
MODES = optin.MODES
RESULTS = ("pass", "fail", "oracle")
VERSION_WARNING = "tests/record.sh: warning:"


def unwarned(status, output, case, overlay):
    """The oracle check of a CPython whose patch version is not .python-version's (--any-python):
    record.sh's warning about it is no failure."""
    kept = [line for line in output.splitlines(keepends=True) if not line.startswith(VERSION_WARNING)]
    return optin.recorded(status, "".join(kept), case, overlay)


def python_ok(version, pinned, any_python):
    """Is CPython version (X.Y.Z) the one .python-version pins, or with --any-python one of its
    minor version."""
    return version == pinned or (any_python and version.rsplit(".", 1)[0] == pinned.rsplit(".", 1)[0])


def rows(cases, modes):
    """Each case's result rows, one per mode: a case whose oracle failed has an 'oracle' row for
    each mode, with the oracle's failure."""
    result = []
    for case in cases:
        if not case["oracle"]:
            result += [{"case": case["case"], "mode": mode, "result": "oracle", "diagnostic": case["failure"]}
                       for mode in modes]
        else:
            result += [{key: row[key] for key in ("case", "mode", "result", "diagnostic")} for row in case["results"]]
    return result


def checks(report):
    """{(case, mode): result} of a report, rejecting a malformed or duplicated row."""
    if not isinstance(report, dict) or report.get("schema") != 1 or not isinstance(report.get("results"), list):
        raise ValueError("not a python-int opt-in report")
    result = {}
    for row in report["results"]:
        if (not isinstance(row, dict) or not isinstance(row.get("case"), str) or row.get("mode") not in MODES or
                row.get("result") not in RESULTS):
            raise ValueError(f"invalid report row: {row!r}")
        key = (row["case"], row["mode"])
        if key in result:
            raise ValueError(f"duplicate report row: {key}")
        result[key] = row["result"]
    return result


def compare(base, new):
    """Of the checks that new ran: those that pass in base and not in new, and those that pass in
    new and failed in base; and the checks of base that new did not run."""
    gone = sorted(k for k in new if new[k] != "pass" and base.get(k) == "pass")
    fixed = sorted(k for k in new if new[k] == "pass" and base.get(k) not in (None, "pass"))
    missing = sorted(k for k in base if k not in new)
    return gone, fixed, missing


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--gate" in argv:
        import python_int_gate
        return python_int_gate.main([arg for arg in argv if arg != "--gate"])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="./pystachy")
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--compare", type=Path, help="an earlier report: fail where its passing checks now fail")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--any-python", action="store_true",
                        help="record with a CPython whose patch version is not .python-version's (for a local "
                             "comparison of two compilers: cases that print the version then fail in both)")
    args = parser.parse_args(argv)
    if (args.jobs < 1 or not 0 < args.timeout < float("inf") or len(args.modes) != len(set(args.modes))):
        parser.error("invalid worker/timeout/mode settings")
    pinned = (ROOT / ".python-version").read_text().strip()
    version = ".".join(map(str, sys.version_info[:3]))
    if not python_ok(version, pinned, args.any_python):
        parser.error(f"run with the exact CPython version pinned by .python-version ({pinned}), "
                     "or with --any-python one of its minor version")
    base = None
    if args.compare is not None:
        try:
            base = checks(optin.load_json(args.compare))
        except (OSError, ValueError) as error:
            parser.error(f"--compare: {error}")
    corpus = optin.programs()
    selected = corpus
    if args.cases is not None:
        if len(args.cases) != len(set(args.cases)) or not set(args.cases) <= set(corpus):
            parser.error("--cases must be unique paths of the differential program corpus")
        selected = [case for case in corpus if case in args.cases]
    digest = optin.corpus_digest(ROOT, corpus)
    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("empty compiler command")
    compiler = shlex.join([str((ROOT / word).resolve()) if (ROOT / word).is_file() else word for word in compiler])
    oracle = unwarned if args.any_python else optin.recorded
    # (as dynany_optin: the harnesses' foreground workers must receive SIGINT)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    with tempfile.TemporaryDirectory(prefix="pystachy-intoptin-") as tmp:
        temp = Path(tmp)
        overlay = temp / "tree"
        optin.prepare_tree(ROOT, overlay, selected, PRAGMA)
        work = temp / "work"
        work.mkdir()
        warm = work / "warm"
        warm.mkdir()
        (warm / "warm.py").write_text("pass\n")
        status, output = optin.run(shlex.split(compiler) + ["run", str(warm / "warm.py")], ROOT,
                                   optin.environment(ROOT, warm), args.timeout)
        if status != 0 or output:
            parser.error(f"compiler/runtime warmup failed (exit {status}): {output}")
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            cases = list(pool.map(lambda case: optin.one(case, ROOT, overlay, work, compiler, args.modes,
                                                         args.timeout, {}, oracle), selected))
    results = rows(cases, args.modes)
    changed = ""
    try:
        if optin.programs() != corpus or optin.corpus_digest(ROOT, corpus) != digest:
            changed = "the corpus changed during execution"
    except ValueError as error:
        changed = str(error)
    report = {"schema": 1, "pragma": PRAGMA.decode().strip(), "python": version, "compiler": compiler,
              "corpus_cases": len(corpus), "corpus_sha256": digest, "modes": args.modes, "cases": selected,
              "subset": args.cases is not None, "checks": len(results),
              "passed_checks": sum(row["result"] == "pass" for row in results),
              "failed_checks": sum(row["result"] != "pass" for row in results), "results": results}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{len(selected)} programs, {report['checks']} checks: {report['passed_checks']} passed, "
          f"{report['failed_checks']} failed")
    if changed != "":
        print("FAIL " + changed)
        return 1
    if base is None:
        return 0
    gone, fixed, missing = compare(base, checks(report))
    print(f"newly failing: {len(gone)}")
    for case, mode in gone:
        row = next(r for r in results if r["case"] == case and r["mode"] == mode)
        print(f"  {case} ({mode}): {row['diagnostic'].splitlines()[0] if row['diagnostic'] else row['result']}")
    print(f"newly passing: {len(fixed)}")
    for case, mode in fixed:
        print(f"  {case} ({mode})")
    if missing:
        print(f"not run here: {len(missing)} checks of {args.compare}")
    return 1 if gone else 0


if __name__ == "__main__":
    raise SystemExit(main())
