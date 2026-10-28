"""Run the differential program corpus with its entry modules opted into dynamic Any.

The temporary tree preserves repository-relative filenames, support modules and sidecars.
Only selected entry modules receive the pragma; imported modules retain their original opt-in
policy. tests/record.sh obtains a fresh pinned-CPython oracle for the changed source (including
line-number/source introspection), then tests/run.sh executes the existing JIT/AOT contract.
Original recordings and source files are never changed. Baseline failures cannot exempt opt-in
failures; the baseline is rerun on a failure to distinguish a regression from a setup problem.

All cases, including stdin, /dev/full and SIGINT fixtures, are selected before deterministic
sharding. Exceptions identify one case/mode and its exact diagnostic; changed failures and
unexpected passes fail. The JSON report is independently checked by verification aggregation.

--native-suite is for a verification run whose tests-native steps execute the unchanged corpus
with the same compiler, JIT and AOT (tests/verify.sh; tools/merge_verification.py requires them
complete). It defers to them only what they already prove: the baseline of an exact expected
failure, and the AOT check of a program whose opted-in LLVM IR is byte-identical to the original's
and whose fresh oracle is byte-identical to its recording ("native-ir" rows). The JIT check of
every program still runs in the opted-in tree.
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

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = "tools/dynany_optin_exceptions.json"
PRAGMA = b"# pystachy: dynamic-any\n"
MODES = ("jit", "aot")
SIDECARS = (".py", ".out", ".err", ".in", ".full", ".path")
COMPILER_DIAGNOSTIC = re.compile(r"[^\n]+\.py:[1-9][0-9]*: error: [^\n]+")


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def load_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid JSON number: {value}")))


def programs(root=ROOT):
    """Use the maintained corpus discovery, not a second independent test glob."""
    result = subprocess.run(["sh", "-c", ". tests/corpus.sh; corpus"], cwd=root,
                            env={**os.environ, "LC_ALL": "C"}, capture_output=True, text=True,
                            check=True, timeout=10)
    paths = [p for p in result.stdout.splitlines() if p.startswith("tests/programs/")]
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("empty or duplicate differential program corpus")
    for path in paths:
        if not re.fullmatch(r"tests/programs/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.py", path):
            raise ValueError(f"invalid corpus path: {path}")
        if not (root / path).is_file() or not (root / path).with_suffix(".out").is_file():
            raise ValueError(f"missing program or recording: {path}")
    return paths


def corpus_digest(root, cases):
    digest = hashlib.sha256()
    for case in cases:
        for suffix in SIDECARS:
            path = Path(case).with_suffix(suffix)
            digest.update(str(path).encode() + b"\0")
            file = root / path
            digest.update(b"present\0" + file.read_bytes() if file.is_file() else b"missing")
            digest.update(b"\0")
    return digest.hexdigest()


def check_inputs(root, cases, digest, manifest_digest):
    if (programs(root) != cases or corpus_digest(root, cases) != digest or
            hashlib.sha256((root / MANIFEST).read_bytes()).hexdigest() != manifest_digest):
        raise ValueError("opt-in inputs changed during execution")


def exceptions(root, cases):
    data = load_json(root / MANIFEST)
    if not isinstance(data, dict) or set(data) != {"schema", "exceptions"} or type(data["schema"]) is not int or data["schema"] != 1:
        raise ValueError("invalid opt-in exception manifest")
    if not isinstance(data["exceptions"], list):
        raise ValueError("exceptions must be a list")
    result = {}
    for row in data["exceptions"]:
        if not isinstance(row, dict) or set(row) != {"case", "mode", "diagnostic", "reason", "issue"}:
            raise ValueError("invalid exception entry")
        if (row["case"] not in cases or row["mode"] not in MODES or
                not all(isinstance(row[k], str) and row[k].strip() for k in ("diagnostic", "reason", "issue")) or
                not re.fullmatch(r"https://github.com/den-run-ai/pystachy/issues/[1-9][0-9]*", row["issue"]) or
                not COMPILER_DIAGNOSTIC.fullmatch(row["diagnostic"])):
            raise ValueError(f"stale or malformed exception: {row}")
        key = (row["case"], row["mode"])
        if key in result:
            raise ValueError(f"duplicate exception: {key}")
        result[key] = row
    return result


def opt_in(source, pragma=PRAGMA):
    """Preserve a BOM and either of Python's first-two-line encoding-cookie positions."""
    bom = b"\xef\xbb\xbf" if source.startswith(b"\xef\xbb\xbf") else b""
    body = source[len(bom):]
    lines = body.splitlines(keepends=True)
    for line in body.split(b"\n"):
        stripped = line.strip()
        if stripped == pragma.strip():
            return source
        if stripped and not stripped.startswith(b"#"):
            break
    at = 0
    for index, line in enumerate(lines[:2]):
        if re.match(br"^[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+", line):
            at = index + 1
    before = b"".join(lines[:at])
    if before and not before.endswith(b"\n"):
        before += b"\n"
    return bom + before + pragma + b"".join(lines[at:])


def prepare_tree(root, target, cases, pragma=PRAGMA):
    target.mkdir(parents=True)
    # Cases read examples and import ports through repository-relative paths. Keep those
    # paths, while giving every writable test/recording an independent copy.
    for entry in root.iterdir():
        if entry.name not in ("tests", ".git", "build"):
            (target / entry.name).symlink_to(entry.resolve(), target_is_directory=entry.is_dir())
    shutil.copytree(root / "tests", target / "tests", symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    for case in cases:
        path = target / case
        if not path.resolve().is_relative_to((target / "tests").resolve()):
            raise ValueError(f"selected source symlink leaves the temporary tests tree: {case}")
        path.write_bytes(opt_in(path.read_bytes(), pragma))


def environment(root, temp):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") and
           k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONUNBUFFERED", "FORCE_COLOR")}
    # Keep only the toolchain choice; GC/optimizer/cache settings cannot weaken this gate.
    if os.environ.get("PYSTACHY_LLVM"):
        env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
    env.update(PYSTACHY_HOME=str(root), PYSTACHY_IRCHECK="1", PYSTACHY_JOBS="1",
               PYSTACHY_GC_STRESS_PROGRAM="0", PYSTACHY_CACHE=str(temp.parent / "cache"),
               PYTHON=sys.executable, TMPDIR=str(temp))
    return env


def run(command, cwd, env, timeout):
    # Each command owns a process group; a timeout kills its descendants too. A foreground
    # subprocess preserves SIGINT handling, unlike shell-backgrounding tests/run.sh.
    with subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, start_new_session=True) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
            return process.returncode, output.decode("utf-8", "replace")
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output, _ = process.communicate()
            return 124, f"timeout after {timeout:g} seconds\n" + output.decode("utf-8", "replace")


def harness_result(status, output, case):
    expected = 2 if Path(case).name.startswith("syntax_") else 1
    lines = output.splitlines()
    if status == 0 and lines == ["selected 1 cases", f"{expected} passed, 0 failed"]:
        return True, ""
    # Do not let exception matching swallow truncated reports or additional failures.
    failure_headers = [line for line in lines if line.startswith("FAIL ")]
    if (status == 1 and len(lines) >= 3 and lines[-2:] ==
            ["selected 1 cases", f"{expected - 1} passed, 1 failed"] and
            len(failure_headers) == 1 and re.fullmatch(
                rf"FAIL {re.escape(Path(case).stem)} \((?:jit|aot)\)", failure_headers[0])):
        diagnostics = [line.strip() for line in lines if ": error: " in line]
        if len(diagnostics) == 1:
            return False, diagnostics[0]
    return False, f"harness exit {status}: " + "\n".join(lines)


def classify(ok, diagnostic, exception, rejection_status=None):
    if exception is None:
        return "pass" if ok else "fail"
    if (ok or rejection_status != b"1\n" or not COMPILER_DIAGNOSTIC.fullmatch(diagnostic) or
            diagnostic != exception["diagnostic"]):
        return "fail"
    return "expected-failure"


def rejection_wrapper(compiler, case, mode, temp):
    """Record the same invocation's exit and streams; a diagnostic cannot exempt a crash."""
    trace = temp / f"{mode}.status"
    trace.unlink(missing_ok=True)
    path = temp / f"{mode}-compiler.sh"
    out, err = temp / f"{mode}.stdout", temp / f"{mode}.stderr"
    action = "run" if mode == "jit" else "build"
    path.write_text("#!/bin/sh\n" +
                    'if [ "$1" = ' + shlex.quote(action) + ' ] && [ "$2" = ' + shlex.quote(case) + ' ]; then\n' +
                    "  " + compiler + ' "$@" > ' + shlex.quote(str(out)) + " 2> " + shlex.quote(str(err)) + "\n" +
                    '  status=$?\n  cat ' + shlex.quote(str(out)) + "\n  cat " + shlex.quote(str(err)) + " >&2\n" +
                    "  printf '%s\\n' \"$status\" >> " + shlex.quote(str(trace)) + "\n  exit \"$status\"\nfi\n" +
                    "exec " + compiler + ' "$@"\n')
    return "sh " + str(path), trace


def rejection_status(trace, diagnostic):
    if trace is None or not trace.is_file():
        return None
    out, err = trace.with_suffix(".stdout"), trace.with_suffix(".stderr")
    if (not out.is_file() or not err.is_file() or out.read_bytes() or
            err.read_bytes() != diagnostic.encode() + b"\n"):
        return None
    return trace.read_bytes()


def recorded(status, output, case, overlay):
    # record.sh's human summary includes the last stdout line. A program can leave that
    # line unfinished ("total: [exit 1]"), and shell echo can expand its backslashes.
    # The fresh recording's terminal exit marker is the reliable boundary.
    path = (overlay / case).with_suffix(".out")
    return (status == 0 and output.startswith(Path(case).stem + ": ") and path.is_file() and
            re.search(br"\[exit [0-9]+\]\n\Z", path.read_bytes()) is not None)


def recording_unchanged(case, root, overlay):
    """Are the overlay's fresh oracle files byte-identical to the case's committed recording?"""
    for suffix in (".out", ".err"):
        old, new = (root / case).with_suffix(suffix), (overlay / case).with_suffix(suffix)
        if old.is_file() != new.is_file() or (old.is_file() and old.read_bytes() != new.read_bytes()):
            return False
    return True


def identical_ir(case, root, overlay, compiler, env, temp, timeout):
    """The sha256 of the case's LLVM IR when the opted-in program's, compiled in the overlay, is
    byte-identical to the original's, compiled in root, each with the import path tests/run.sh
    gives it; None otherwise (including any compiler failure or output)."""
    texts = []
    for tree, name in ((root, "original"), (overlay, "optin")):
        tree_env = dict(env)
        if (tree / case).with_suffix(".path").is_file():
            scratch = temp / f"{name}-path"
            scratch.mkdir(exist_ok=True)
            status, output = run(["sh", "tests/prepare_path.sh", case, str(scratch)], tree, env, timeout)
            if status != 0 or len(output.splitlines()) != 1:
                return None
            tree_env["PYSTACHY_PATH"] = output.rstrip("\n")
        ir = temp / f"{name}.ll"
        ir.unlink(missing_ok=True)
        status, output = run(shlex.split(compiler) + ["ir", case, "-o", str(ir)], tree, tree_env, timeout)
        if status != 0 or output or not ir.is_file():
            return None
        texts.append(ir.read_bytes())
        ir.unlink()
    return hashlib.sha256(texts[0]).hexdigest() if texts[0] == texts[1] else None


def native_ir(case, root, overlay, compiler, env, temp, timeout, modes, allowed):
    """The IR digest that lets tests-native's AOT check of the unchanged program stand for this
    case's (see --native-suite), or None: never for an excepted AOT check or a changed oracle."""
    if "aot" not in modes or (case, "aot") in allowed or not recording_unchanged(case, root, overlay):
        return None
    return identical_ir(case, root, overlay, compiler, env, temp, timeout)


def one(case, root, overlay, temp, compiler, modes, timeout, allowed, oracle=recorded, native=False):
    case_temp = temp / Path(case).stem
    case_temp.mkdir()
    env = environment(root, case_temp)
    # Require this invocation to create its own oracle, not leave a copied recording behind.
    for suffix in (".out", ".err"):
        (overlay / case).with_suffix(suffix).unlink(missing_ok=True)
    status, output = run(["sh", "tests/record.sh", case], overlay, env, timeout)
    if not oracle(status, output, case, overlay):
        return {"case": case, "oracle": False, "results": [],
                "failure": f"{case}: oracle exit {status}: {output.strip()}"}
    rows = []
    same = native_ir(case, root, overlay, compiler, env, case_temp, timeout, modes, allowed) if native else None
    for mode in modes:
        if mode == "aot" and same is not None:
            rows.append({"case": case, "mode": mode, "result": "native-ir", "diagnostic": ""})
            continue
        exception = allowed.get((case, mode))
        checked_compiler, trace = (rejection_wrapper(compiler, case, mode, case_temp)
                                   if exception is not None else (compiler, None))
        command = ["sh", "tests/run.sh", checked_compiler, mode, case]
        status, output = run(command, overlay, env, timeout)
        ok, diagnostic = harness_result(status, output, case)
        rejected = rejection_status(trace, diagnostic)
        result = classify(ok, diagnostic, exception, rejected)
        if exception is not None and not ok and rejected != b"1\n":
            diagnostic += f"\nexpected one compiler exit 1 with only its exact diagnostic, recorded {rejected!r}"
        row = {"case": case, "mode": mode, "result": result, "diagnostic": diagnostic}
        # (with --native-suite, tests-native runs the unchanged program in this mode)
        if not ok and not (native and result == "expected-failure"):
            baseline_status, baseline_output = run(["sh", "tests/run.sh", compiler, mode, case], root, env, timeout)
            baseline_ok, baseline_diagnostic = harness_result(baseline_status, baseline_output, case)
            if not baseline_ok:
                row["result"] = "fail"
                row["diagnostic"] += "\nbaseline also fails: " + baseline_diagnostic
        elif exception is not None:
            row["diagnostic"] = "unexpected pass: remove the obsolete exception"
        rows.append(row)
    return {"case": case, "oracle": True, "results": rows}


def positive_int(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label}: expected integer >= {minimum}")
    return value


def validate_report(report, root=ROOT):
    """Reject partial, stale, duplicated, fabricated-success or development-only reports."""
    if not isinstance(report, dict):
        raise ValueError("opt-in report must be an object")
    corpus = programs(root)
    allowed = exceptions(root, corpus)
    if positive_int(report.get("schema"), "schema") != 1:
        raise ValueError("unknown opt-in report schema")
    count = positive_int(report.get("shard_count"), "shard_count", 1)
    index = positive_int(report.get("shard_index"), "shard_index")
    if index >= count:
        raise ValueError("shard_index out of range")
    selected = corpus[index::count]
    if not selected or report.get("cases") != selected or report.get("subset") is not False:
        raise ValueError("opt-in report does not cover exactly its full corpus shard")
    if report.get("modes") != list(MODES):
        raise ValueError("opt-in report must execute JIT and AOT")
    native = report.get("native_suite")
    if type(native) is not bool:
        raise ValueError("opt-in report must state whether it defers to tests-native")
    expected = [(case, mode) for case in selected for mode in MODES]
    if (positive_int(report.get("corpus_cases"), "corpus_cases") != len(corpus) or
            report.get("corpus_sha256") != corpus_digest(root, corpus) or
            report.get("exceptions_sha256") != hashlib.sha256((root / MANIFEST).read_bytes()).hexdigest()):
        raise ValueError("opt-in corpus/exception identity changed")
    for key, wanted in (("oracle_cases", len(selected)), ("expected_checks", len(expected)),
                        ("completed_checks", len(expected))):
        if positive_int(report.get(key), key) != wanted:
            raise ValueError(f"opt-in {key} incomplete")
    rows = report.get("results")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("missing opt-in result rows")
    if report.get("failures") != []:
        raise ValueError("opt-in report contains failures")
    passed = known = same = 0
    for row, (case, mode) in zip(rows, expected):
        if not isinstance(row, dict) or set(row) != {"case", "mode", "result", "diagnostic"}:
            raise ValueError("invalid opt-in result row")
        if row["case"] != case or row["mode"] != mode:
            raise ValueError("opt-in case/mode missing, duplicated or reordered")
        exception = allowed.get((case, mode))
        if exception is None and native and mode == "aot" and row["result"] == "native-ir" and row["diagnostic"] == "":
            same += 1
        elif exception is None:
            if row["result"] != "pass" or row["diagnostic"] != "":
                raise ValueError(f"unexpected opt-in failure: {case} ({mode})")
            passed += 1
        else:
            if row["result"] != "expected-failure" or row["diagnostic"] != exception["diagnostic"]:
                raise ValueError(f"changed or obsolete opt-in exception: {case} ({mode})")
            known += 1
    if (positive_int(report.get("passed_checks"), "passed_checks") != passed or
            positive_int(report.get("expected_failures"), "expected_failures") != known or
            positive_int(report.get("native_ir_checks"), "native_ir_checks") != same):
        raise ValueError("opt-in result counts disagree")


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
    parser.add_argument("--native-suite", action="store_true",
                        help="defer to the same verification run's tests-native steps (see above)")
    args = parser.parse_args(argv)
    if (args.jobs < 1 or args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count or
            not 0 < args.timeout < float("inf") or len(args.modes) != len(set(args.modes))):
        parser.error("invalid worker/shard/timeout/mode settings")
    if ".".join(map(str, sys.version_info[:3])) != (ROOT / ".python-version").read_text().strip():
        parser.error("run with the exact CPython version pinned by .python-version")
    corpus = programs()
    allowed = exceptions(ROOT, corpus)
    digest = corpus_digest(ROOT, corpus)
    manifest_digest = hashlib.sha256((ROOT / MANIFEST).read_bytes()).hexdigest()
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
    compiler = shlex.join(compiler)
    # An asynchronous caller may have ignored SIGINT. Reset it before spawning harnesses:
    # their foreground worker must receive the signal used by the SIGINT corpus cases.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    with tempfile.TemporaryDirectory(prefix="pystachy-optin-") as tmp:
        temp = Path(tmp)
        overlay = temp / "tree"
        prepare_tree(ROOT, overlay, selected)
        work = temp / "work"
        work.mkdir()
        warm = work / "warm"
        warm.mkdir()
        (warm / "warm.py").write_text("pass\n")
        status, output = run(shlex.split(compiler) + ["run", str(warm / "warm.py")], ROOT,
                             environment(ROOT, warm), args.timeout)
        if status != 0 or output:
            parser.error(f"compiler/runtime warmup failed (exit {status}): {output}")
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(one, case, ROOT, overlay, work, compiler, args.modes,
                                   args.timeout, allowed, native=args.native_suite) for case in selected]
            cases = []
            for future in futures:
                result = future.result()
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
            check_inputs(ROOT, corpus, digest, manifest_digest)
        except ValueError as error:
            failures.append(str(error))
        report = {"schema": 1, "corpus_cases": len(corpus), "corpus_sha256": digest,
                  "exceptions_sha256": manifest_digest,
                  "shard_index": args.shard_index, "shard_count": args.shard_count,
                  "modes": args.modes, "native_suite": args.native_suite, "cases": selected,
                  "subset": args.cases is not None, "oracle_cases": sum(case["oracle"] for case in cases),
                  "expected_checks": len(selected) * len(args.modes), "completed_checks": len(rows),
                  "passed_checks": sum(row["result"] == "pass" for row in rows),
                  "expected_failures": sum(row["result"] == "expected-failure" for row in rows),
                  "native_ir_checks": sum(row["result"] == "native-ir" for row in rows),
                  "failures": failures, "results": rows}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        if args.keep:
            shutil.copytree(overlay, args.keep, symlinks=True)
    print(f"{len(selected)} programs, {report['completed_checks']} checks: "
          f"{report['passed_checks']} passed, {report['native_ir_checks']} AOT checks of unchanged IR left to "
          f"tests-native, {report['expected_failures']} expected failures, {len(failures)} failures")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
