"""Enforce reviewed python-int compatibility exceptions against fresh CPython recordings.

Only exact compiler rejections can be excepted. A timeout, crash, changed output, changed
error, failed baseline or oracle, and an obsolete exception all fail. Exploratory reports
from python_int_optin.py are deliberately not release/verification evidence.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile

import dynany_optin as optin

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = "tools/python_int_optin_exceptions.json"
PRAGMA = b"# pystachy: python-int\n"
MODES = optin.MODES
CATEGORIES = ("dynamic-any-conflict", "unsupported-identity", "unsupported-storage", "unsupported-builtin",
              "unsupported-protocol", "unsupported-call", "unsupported-annotation", "unsupported-inference")
INPUT_DIRS = ("src", "lib", "tools", "tests", "mpz", "ryu", "examples", "ports", "bench")
SOURCE_SUFFIXES = {".py", ".pyi", ".c", ".h", ".sh", ".json", ".path", ".out", ".err", ".in", ".full",
                   ".txt", ".yml", ".yaml", ".toml", ".ini"}
SHA256 = re.compile(r"[0-9a-f]{64}")
programs = optin.programs


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(root):
    """Working-tree inputs, including untracked/ignored importable support modules.

    Tracked files bind the complete source checkout. Extra source files are included even
    when ignored: git status alone cannot certify which library modules were consumed.
    Build products and bytecode are excluded; the executed compiler is hashed separately.
    """
    root = root.resolve()
    ignored = {"__pycache__", ".git", ".venv", "build"}
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True, timeout=30)
    names = {os.fsdecode(name) for name in result.stdout.split(b"\0") if name}
    def directory_link(path):
        if path.is_symlink():
            target = path.resolve()
            if (not target.is_relative_to(root) or not target.relative_to(root).parts or
                    target.relative_to(root).parts[0] not in INPUT_DIRS or
                    any(part in ignored for part in target.relative_to(root).parts)):
                raise ValueError(f"source directory link leaves fingerprinted inputs: {path.relative_to(root)}")
            names.add(path.relative_to(root).as_posix())

    for directory in INPUT_DIRS:
        directory_link(root / directory)
        for base, dirs, files in os.walk(root / directory, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in ignored)
            for name in dirs:
                directory_link(Path(base) / name)
            for name in files:
                path = Path(base) / name
                if path.suffix in SOURCE_SUFFIXES:
                    names.add(path.relative_to(root).as_posix())
    for path in root.iterdir():
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            names.add(path.name)
    digest = hashlib.sha256()
    for name in sorted(names):
        path = root / name
        if path.is_symlink():
            data, kind = os.fsencode(os.readlink(path)), b"link"
            # Bind regular link targets too, while retaining deliberately dangling/cyclic
            # fixture links. Directory links are accounted for by their tracked target files.
            if path.is_file():
                data += b"\0" + path.read_bytes()
        else:
            data = path.read_bytes()
            kind = b"executable" if path.stat().st_mode & 0o111 else b"file"
        digest.update(name.encode() + b"\0" + kind + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()


def exceptions(root, cases):
    data = optin.load_json(root / MANIFEST)
    if (not isinstance(data, dict) or set(data) != {"schema", "exceptions"} or
            type(data["schema"]) is not int or data["schema"] != 1 or not isinstance(data["exceptions"], list)):
        raise ValueError("invalid python-int exception manifest")
    result = {}
    fields = {"case", "mode", "category", "diagnostic", "reason", "issue"}
    for row in data["exceptions"]:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("invalid python-int exception entry")
        if (row["case"] not in cases or row["mode"] not in MODES or row["category"] not in CATEGORIES or
                not all(isinstance(row[k], str) and row[k].strip() for k in fields) or
                not re.fullmatch(r"https://github.com/den-run-ai/pystachy/issues/[1-9][0-9]*", row["issue"]) or
                not optin.COMPILER_DIAGNOSTIC.fullmatch(row["diagnostic"])):
            raise ValueError(f"stale or malformed python-int exception: {row}")
        key = (row["case"], row["mode"])
        if key in result:
            raise ValueError(f"duplicate python-int exception: {key}")
        result[key] = row
    return result


def normalize_diagnostic(diagnostic, root):
    """Remove only this checkout's prefix from an existing compiler-source filename.

    Absolute imported-library locations vary with the checkout. Error text, other paths,
    traversal spellings and the original stderr captured for rejection proof stay intact.
    """
    if not optin.COMPILER_DIAGNOSTIC.fullmatch(diagnostic):
        return diagnostic
    filename, separator, tail = diagnostic.partition(":")
    prefix = str(root.resolve()) + "/"
    if filename.startswith(prefix):
        relative = filename[len(prefix):]
        parts = relative.split("/")
        if all(part not in ("", ".", "..") for part in parts) and (root / relative).is_file():
            return relative + separator + tail
    return diagnostic


def one(case, root, overlay, temp, compiler, modes, timeout, allowed, gc_stress=False):
    # Case-relative directories also prevent same-stem programs from sharing traces.
    case_temp = temp / Path(case).with_suffix("")
    case_temp.mkdir(parents=True)
    env = optin.environment(root, case_temp)
    env["PYSTACHY_CACHE"] = str(temp / "cache")
    env["PYSTACHY_GC_STRESS_PROGRAM"] = "1" if gc_stress else "0"
    for suffix in (".out", ".err"):
        (overlay / case).with_suffix(suffix).unlink(missing_ok=True)
    status, output = optin.run(["sh", "tests/record.sh", case], overlay, env, timeout)
    evidence = {"case": case, "oracle": {"status": status, "output": output}, "modes": []}
    if not optin.recorded(status, output, case, overlay):
        result = {"case": case, "oracle": False, "results": [],
                  "failure": f"{case}: oracle exit {status}: {output.strip()}"}
    else:
        rows = []
        for mode in modes:
            exception = allowed.get((case, mode))
            # Only a reviewed compiler rejection may redirect compiler streams. An
            # ordinary JIT case may deliberately write to /dev/full or receive SIGINT.
            checked_compiler, trace = (optin.rejection_wrapper(compiler, case, mode, case_temp)
                                       if exception is not None else (compiler, None))
            status, output = optin.run(["sh", "tests/run.sh", checked_compiler, mode, case], overlay, env, timeout)
            ok, observed = optin.harness_result(status, output, case)
            # Verify the exact original stderr before making only its filename portable.
            rejected = optin.rejection_status(trace, observed)
            diagnostic = normalize_diagnostic(observed, root)
            result = optin.classify(ok, diagnostic, exception, rejected)
            detail = {"mode": mode, "harness_status": status, "harness_output": output,
                      "compiler_status": trace.read_text() if trace is not None and trace.is_file() else None,
                      "compiler_stdout": trace.with_suffix(".stdout").read_text(errors="replace")
                      if trace is not None and trace.with_suffix(".stdout").is_file() else None,
                      "compiler_stderr": trace.with_suffix(".stderr").read_text(errors="replace")
                      if trace is not None and trace.with_suffix(".stderr").is_file() else None}
            if exception is not None and not ok and rejected != b"1\n":
                diagnostic += f"\nexpected one compiler exit 1 with only its exact diagnostic, recorded {rejected!r}"
            row = {"case": case, "mode": mode, "result": result, "diagnostic": diagnostic}
            if not ok:
                base_status, base_output = optin.run(["sh", "tests/run.sh", compiler, mode, case], root, env, timeout)
                base_ok, base_diagnostic = optin.harness_result(base_status, base_output, case)
                detail["baseline"] = {"status": base_status, "output": base_output}
                if not base_ok:
                    row["result"] = "fail"
                    row["diagnostic"] += "\nbaseline also fails: " + base_diagnostic
            elif exception is not None:
                row["diagnostic"] = "unexpected pass: remove the obsolete exception"
            rows.append(row)
            evidence["modes"].append(detail)
        result = {"case": case, "oracle": True, "results": rows}
    (case_temp / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return result


def validate_report(report, root=ROOT):
    """Independently validate a complete normal-GC JIT+AOT corpus shard.

    Development subsets, alternate Python versions and GC-focused runs cannot stand in
    for this gate. The outer verification harness binds compiler_sha256 to its verified
    bootstrap binary; it must also check all shard indexes, not just each shard alone.
    """
    if not isinstance(report, dict) or report.get("kind") != "python-int-gate":
        raise ValueError("not a python-int gate report")
    if optin.positive_int(report.get("schema"), "schema") != 1 or report.get("pragma") != PRAGMA.decode().strip():
        raise ValueError("invalid python-int gate schema or pragma")
    corpus = programs(root)
    allowed = exceptions(root, corpus)
    count = optin.positive_int(report.get("shard_count"), "shard_count", 1)
    index = optin.positive_int(report.get("shard_index"), "shard_index")
    if index >= count:
        raise ValueError("python-int shard_index out of range")
    selected = corpus[index::count]
    if not selected or report.get("cases") != selected or report.get("subset") is not False:
        raise ValueError("python-int report does not cover exactly its full corpus shard")
    if report.get("modes") != list(MODES) or report.get("gc_stress") is not False:
        raise ValueError("python-int report must execute normal-GC JIT and AOT")
    if report.get("python") != (root / ".python-version").read_text().strip():
        raise ValueError("python-int oracle version differs from pinned CPython")
    if not isinstance(report.get("compiler_sha256"), str) or not SHA256.fullmatch(report["compiler_sha256"]):
        raise ValueError("missing python-int compiler identity")
    identities = {"corpus_sha256": optin.corpus_digest(root, corpus), "exceptions_sha256": sha256(root / MANIFEST),
                  "source_sha256": source_digest(root)}
    if any(report.get(key) != value for key, value in identities.items()):
        raise ValueError("python-int source/corpus/exception identity changed")
    expected = [(case, mode) for case in selected for mode in MODES]
    for key, wanted in (("corpus_cases", len(corpus)), ("oracle_cases", len(selected)),
                        ("expected_checks", len(expected)), ("completed_checks", len(expected))):
        if optin.positive_int(report.get(key), key) != wanted:
            raise ValueError(f"python-int {key} incomplete")
    rows = report.get("results")
    if not isinstance(rows, list) or len(rows) != len(expected) or report.get("failures") != []:
        raise ValueError("python-int results missing or contain failures")
    passed = known = 0
    for row, (case, mode) in zip(rows, expected):
        if not isinstance(row, dict) or set(row) != {"case", "mode", "result", "diagnostic"}:
            raise ValueError("invalid python-int result row")
        if (row["case"], row["mode"]) != (case, mode):
            raise ValueError("python-int case/mode missing, duplicated or reordered")
        exception = allowed.get((case, mode))
        if exception is None:
            if row["result"] != "pass" or row["diagnostic"] != "":
                raise ValueError(f"unexpected python-int failure: {case} ({mode})")
            passed += 1
        else:
            if row["result"] != "expected-failure" or row["diagnostic"] != exception["diagnostic"]:
                raise ValueError(f"changed or obsolete python-int exception: {case} ({mode})")
            known += 1
    if (optin.positive_int(report.get("passed_checks"), "passed_checks") != passed or
            optin.positive_int(report.get("expected_failures"), "expected_failures") != known):
        raise ValueError("python-int result counts disagree")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="./pystachy")
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--keep", type=Path)
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--gc-stress", action="store_true")
    args = parser.parse_args(argv)
    if (args.jobs < 1 or args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count or
            not 0 < args.timeout < float("inf") or len(args.modes) != len(set(args.modes))):
        parser.error("invalid worker/shard/timeout/mode settings")
    version = ".".join(map(str, sys.version_info[:3]))
    if version != (ROOT / ".python-version").read_text().strip():
        parser.error("run with the exact CPython version pinned by .python-version")
    corpus = programs(ROOT)
    allowed = exceptions(ROOT, corpus)
    selected = corpus[args.shard_index::args.shard_count]
    if args.cases is not None:
        if not args.cases or len(args.cases) != len(set(args.cases)) or not set(args.cases) <= set(selected):
            parser.error("--cases must be unique paths belonging to the selected corpus shard")
        selected = [case for case in selected if case in args.cases]
    if not selected:
        parser.error("empty corpus shard")
    compiler = shlex.split(args.compiler)
    if not compiler:
        parser.error("empty compiler command")
    compiler = [str((ROOT / word).resolve()) if (ROOT / word).is_file() else word for word in compiler]
    executable = shutil.which(compiler[0])
    if executable is None:
        parser.error("compiler executable not found")
    identities = {"corpus_sha256": optin.corpus_digest(ROOT, corpus), "exceptions_sha256": sha256(ROOT / MANIFEST),
                  "source_sha256": source_digest(ROOT), "compiler_sha256": sha256(Path(executable))}
    compiler = shlex.join(compiler)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    with tempfile.TemporaryDirectory(prefix="pystachy-intgate-") as tmp:
        temp = Path(tmp)
        overlay, work = temp / "tree", temp / "work"
        optin.prepare_tree(ROOT, overlay, selected, PRAGMA)
        work.mkdir()
        warm = work / "warm"
        warm.mkdir()
        (warm / "warm.py").write_text("pass\n")
        status, output = optin.run(shlex.split(compiler) + ["run", str(warm / "warm.py")], ROOT,
                                   optin.environment(ROOT, warm), args.timeout)
        if status != 0 or output:
            parser.error(f"compiler/runtime warmup failed (exit {status}): {output}")
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(one, case, ROOT, overlay, work, compiler, args.modes,
                                   args.timeout, allowed, args.gc_stress) for case in selected]
            cases = []
            for case, future in zip(selected, futures):
                try:
                    result = future.result()
                except Exception as error:
                    result = {"case": case, "oracle": False, "results": [],
                              "failure": f"{case}: worker {type(error).__name__}: {error}"}
                cases.append(result)
                for row in result["results"]:
                    if row["result"] != "pass":
                        print(f"{row['result'].upper()} {row['case']} ({row['mode']}): {row['diagnostic']}", flush=True)
                if not result["oracle"]:
                    print("FAIL " + result["failure"], flush=True)
        rows = [row for case in cases for row in case["results"]]
        failures = [case["failure"] for case in cases if not case["oracle"]]
        failures += [f"{row['case']} ({row['mode']}): {row['diagnostic']}" for row in rows if row["result"] == "fail"]
        try:
            current = {"corpus_sha256": optin.corpus_digest(ROOT, corpus), "exceptions_sha256": sha256(ROOT / MANIFEST),
                       "source_sha256": source_digest(ROOT), "compiler_sha256": sha256(Path(executable))}
            if programs(ROOT) != corpus or current != identities:
                failures.append("python-int inputs changed during execution")
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append(f"could not revalidate python-int inputs: {error}")
        report = {"schema": 1, "kind": "python-int-gate", "pragma": PRAGMA.decode().strip(), "python": version,
                  "compiler": compiler, **identities, "corpus_cases": len(corpus),
                  "shard_index": args.shard_index, "shard_count": args.shard_count, "gc_stress": args.gc_stress,
                  "modes": args.modes, "cases": selected, "subset": args.cases is not None,
                  "oracle_cases": sum(case["oracle"] for case in cases),
                  "expected_checks": len(selected) * len(args.modes), "completed_checks": len(rows),
                  "passed_checks": sum(row["result"] == "pass" for row in rows),
                  "expected_failures": sum(row["result"] == "expected-failure" for row in rows),
                  "failures": failures, "results": rows}
        if args.cases is None and args.modes == list(MODES) and not args.gc_stress and not failures:
            try:
                validate_report(report, ROOT)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                failures.append(f"invalid python-int gate evidence: {error}")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        if args.keep:
            args.keep.mkdir(parents=True, exist_ok=True)
            shutil.copytree(overlay / "tests", args.keep / "tests", symlinks=True)
            shutil.copytree(work, args.keep / "evidence", symlinks=True, ignore=shutil.ignore_patterns("cache"))
    print(f"{len(selected)} programs, {report['completed_checks']} checks: {report['passed_checks']} passed, "
          f"{report['expected_failures']} expected failures, {len(failures)} failures")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
