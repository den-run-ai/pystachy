"""Qualify selected upstream unittest methods before and after pytest extraction.

Original sources and support modules are hash-pinned. Optional sources are fetched
only with --fetch, then reused offline. A passing adapted suite alone cannot pass
this check: original unittest, real pytest and generated CPython must agree first.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import shlex
import subprocess
import sys
import tempfile
import unittest
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/upstream/pytest/manifest.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment(imports=()):
    allowed = {"PYSTACHY_LLVM", "PYSTACHY_CACHE", "PYSTACHY_JOBS"}
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PYTHON", "PYTEST", "PYSTACHY_")) or key in allowed}
    paths = os.pathsep.join(str(path) for path in imports)
    env.update(PYTHONPATH=paths, PYTHONDONTWRITEBYTECODE="1", PYSTACHY_PATH=paths, PYSTACHY_HOME=str(ROOT))
    return env


def source_files(manifest, suite, cache, fetch=False):
    """Check bytes before use; failed/mismatched downloads never replace a file."""
    files = {}
    for name in suite["files"]:
        entry = manifest["files"][name]
        path = ROOT / entry["local"] if "local" in entry else cache / name
        if not path.exists() and fetch and "url" in entry:
            with urlopen(entry["url"], timeout=30) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError("download hash mismatch: " + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if not path.is_file():
            raise ValueError(f"missing pinned source {path}; use --fetch once or provide --source-cache")
        if sha256(path) != entry["sha256"]:
            raise ValueError("source hash mismatch: " + str(path))
        files[name] = {"path": str(path.resolve()), "sha256": entry["sha256"],
                       "url": entry.get("url", entry.get("upstream"))}
    return files


def original_report(source, selected, imports, reference_modules=None):
    """Executed only in an isolated CPython subprocess, using real unittest."""
    sys.path[:0] = [str(path) for path in imports]
    reference_modules = reference_modules or {}
    roots = {name.split(".")[0] for name in reference_modules}
    # A site initialization may already have imported the host copy. Reload
    # only the explicitly pinned application packages from the fresh snapshot.
    for name in list(sys.modules):
        if name.split(".")[0] in roots:
            del sys.modules[name]
    module_name = "_pystachy_original_unittest"
    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    loaded = {}
    for name, identity in reference_modules.items():
        imported = sys.modules.get(name)
        origin = getattr(imported, "__file__", None)
        if origin is None or Path(origin).resolve() != Path(identity["path"]).resolve():
            raise ValueError("original implementation came from an unexpected path: " + name)
        loaded[name] = {"path": str(Path(origin).resolve()), "sha256": sha256(Path(origin))}
        if loaded[name] != identity:
            raise ValueError("original implementation source identity differs: " + name)
    loader = unittest.TestLoader()

    def case_id(test):
        value = test.id()
        return value.removeprefix(module_name + ".")

    def flatten(suite):
        for case in suite:
            if isinstance(case, unittest.TestSuite):
                yield from flatten(case)
            else:
                yield case_id(case)

    # Keep custom-collection/doctest IDs in the original inventory even though
    # the explicit selection below runs only the requested unittest methods.
    inventory = list(flatten(loader.loadTestsFromModule(module)))
    if loader.errors or len(inventory) != len(set(inventory)):
        raise ValueError("original unittest inventory failed or contains duplicate IDs")
    if not selected or len(selected) != len(set(selected)) or any(name not in inventory for name in selected):
        raise ValueError("original selected methods are empty, duplicated or missing")

    class Result(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.outcomes = []
            self.active = None

        def startTest(self, test):
            super().startTest(test)
            random.seed(0)  # Same explicit per-method seed as the extractor.
            self.active = {"case": case_id(test), "outcome": "running", "subtests": 0}

        def stopTest(self, test):
            self.outcomes.append(self.active)
            self.active = None
            super().stopTest(test)

        def addSuccess(self, test):
            super().addSuccess(test)
            self.active["outcome"] = "passed"

        def addFailure(self, test, err):
            super().addFailure(test, err)
            self.active["outcome"] = "failed"

        def addError(self, test, err):
            super().addError(test, err)
            if self.active is not None:
                self.active["outcome"] = "error"

        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            if self.active is not None:
                self.active["outcome"] = "skipped"

        def addExpectedFailure(self, test, err):
            super().addExpectedFailure(test, err)
            self.active["outcome"] = "xfailed"

        def addUnexpectedSuccess(self, test):
            super().addUnexpectedSuccess(test)
            self.active["outcome"] = "xpassed"

        def addSubTest(self, test, subtest, err):
            super().addSubTest(test, subtest, err)
            self.active["subtests"] += 1
            if err is not None:
                self.active["outcome"] = "failed"

    tests = []
    for item in selected:
        class_name, method = item.split(".", 1)
        cls = getattr(module, class_name)
        if not isinstance(cls, type) or not issubclass(cls, unittest.TestCase):
            raise ValueError("selected item is not an original TestCase: " + item)
        tests.append(cls(method))
    result = Result()
    unittest.TestSuite(tests).run(result)
    successful = (result.wasSuccessful() and not result.skipped and not result.expectedFailures
                  and len(result.outcomes) == len(selected)
                  and all(row["outcome"] == "passed" for row in result.outcomes))
    return {"complete": True, "exit_code": 0 if successful else 1, "python": sys.version,
            "source_sha256": sha256(source), "reference_modules": loaded,
            "inventory": inventory, "selected": selected,
            "outcomes": result.outcomes, "tests_run": result.testsRun,
            "failures": [{"case": case_id(test), "detail": text} for test, text in result.failures],
            "errors": [{"case": case_id(test), "detail": text} for test, text in result.errors],
            "seed": 0}


def validate_original(report, selected, source_hash, inventory):
    if (type(report) is not dict or report.get("complete") is not True or report.get("exit_code") != 0
            or report.get("source_sha256") != source_hash or report.get("selected") != selected
            or report.get("tests_run") != len(selected) or report.get("inventory") != inventory):
        raise ValueError("original unittest identity, inventory or completion differs")
    outcomes = report.get("outcomes", [])
    if ([row["case"] for row in outcomes] != selected
            or any(row["outcome"] != "passed" for row in outcomes)
            or report.get("errors") or report.get("failures")):
        raise ValueError("every original selected unittest method must execute and pass")


def validate_adapted(evidence, selected, mode, status):
    # Import only in the hosted controller; the original test subprocess does
    # not import pytest, transformed source or generated support modules.
    import pytest_native as runner

    expected = ["test_selected.py::test_" + name.replace(".", "__") for name in selected]
    results = [runner.Result(**row) for row in evidence["results"]]
    if (evidence.get("mode") != mode or evidence.get("exit_code") != status or status != 0
            or [case for row in results for case in row.cases] != expected
            or any(row.state != "passed" for row in results)
            or not evidence.get("oracle") or evidence["oracle"].get("exit_code") != 0
            or evidence.get("differences")):
        raise ValueError("adapted suite identity, inventory or completion differs")
    if runner.compare(results, evidence["oracle"]):
        raise ValueError("adapted pytest and generated execution disagree")
    events = [event for row in results for event in row.events]
    expected_events = [(case, phase) for case in expected for phase in ("setup", "call", "teardown")]
    if ([(event["nodeid"], event["phase"]) for event in events] != expected_events
            or any(event["outcome"] != "passed" for event in events)):
        raise ValueError("every adapted test and phase must execute and pass")


def qualify(name, spec, manifest, args):
    import cpython_test_methods as extractor

    row = {"suite": name, "state": "error", "selected": spec["selected"], "modes": []}
    work = args.work_dir.resolve() / name
    work.mkdir(parents=True, exist_ok=True)
    try:
        files = source_files(manifest, spec, args.source_cache.resolve(), args.fetch)
        row["sources"] = files
        # Import a new snapshot containing only pinned files. Ignored pycs,
        # extension modules and extra importable files in a caller's cache must
        # never shadow the source whose hash we just checked.
        snapshot = Path(tempfile.mkdtemp(prefix="sources-", dir=work))
        for name, identity in files.items():
            data = Path(identity["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != identity["sha256"]:
                raise ValueError("source changed while creating snapshot: " + name)
            dest = snapshot / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        row["source_snapshot"] = str(snapshot)
        source = snapshot / spec["source"]
        imports = [snapshot / value for value in spec.get("original_imports", [])]
        generated_imports = [snapshot / value for value in spec.get("adapted_imports", [])]
        request = work / "original-request.json"
        reference_modules = {name: {"path": str(snapshot / path), "sha256": files[path]["sha256"]}
                             for name, path in spec.get("reference_modules", {}).items()}
        request.write_text(json.dumps({"source": str(source), "selected": spec["selected"],
                                       "imports": [str(path) for path in imports],
                                       "reference_modules": reference_modules}))
        original_path = work / "original.json"
        original_path.unlink(missing_ok=True)
        command = [args.python, "-I", "-B", str(Path(__file__).resolve()), "_original",
                   str(request), str(original_path)]
        ran = subprocess.run(command, cwd=ROOT, env=environment(), capture_output=True, text=True,
                             timeout=args.timeout)
        row["original_process"] = {"exit_code": ran.returncode, "stdout": ran.stdout, "stderr": ran.stderr}
        original = json.loads(original_path.read_text())
        row["original"] = original
        if ran.returncode != original.get("exit_code"):
            raise ValueError("original report and process exit status differ")
        if original.get("reference_modules") != reference_modules:
            raise ValueError("original implementation identity is missing or differs")
        validate_original(original, spec["selected"], files[spec["source"]]["sha256"], spec["inventory"])
        output = Path(tempfile.mkdtemp(prefix="adapted-", dir=work)) / "suite"
        extraction = extractor.pytest_suite(source, output, [tuple(name.split(".", 1)) for name in spec["selected"]],
                                           selected_methods_only=True)
        row["extraction"] = extraction
        row["mapping"] = [{"original": item, "adapted": "test_selected.py::test_" + item.replace(".", "__")}
                          for item in spec["selected"]]
        row["excluded"] = [{"case": case, "reason": spec["exclusion_reason"]}
                           for case in original["inventory"] if case not in spec["selected"]]
        for excluded in row["excluded"]:
            excluded["reason"] = spec.get("exclusions", {}).get(excluded["case"], excluded["reason"])
        row["adapted_sources"] = {path.name: sha256(path) for path in sorted(output.glob("*.py"))}
        # Generated CPython always precedes native execution. This keeps
        # extraction mistakes separate from compiler/library incompatibility.
        for mode in dict.fromkeys(["python", *args.mode]):
            report = work / (mode + ".json")
            report.unlink(missing_ok=True)
            command = [sys.executable, str(ROOT / "tools/pytest_native.py"), str(output / "test_selected.py"),
                       "--root", str(output), "--work-dir", str(output.parent / mode), "--mode", mode,
                       "--compare", "--python", args.python, "--compiler", args.compiler,
                       "--timeout", str(args.timeout), "--json", str(report)]
            ran = subprocess.run(command, cwd=ROOT, env=environment(generated_imports), capture_output=True,
                                 text=True, timeout=3 * args.timeout + 30)
            mode_row = {"mode": mode, "exit_code": ran.returncode, "stdout": ran.stdout, "stderr": ran.stderr}
            row["modes"].append(mode_row)
            evidence = json.loads(report.read_text())
            mode_row["evidence"] = evidence
            validate_adapted(evidence, spec["selected"], mode, ran.returncode)
        row["state"] = "passed"
    except (OSError, ValueError, KeyError, TypeError, extractor.Unsupported, subprocess.TimeoutExpired) as error:
        row["error"] = str(error)
    return row


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_original"]:
        request = json.loads(Path(argv[1]).read_text())
        report = original_report(Path(request["source"]), request["selected"], request["imports"],
                                 request.get("reference_modules"))
        Path(argv[2]).write_text(json.dumps(report, indent=2) + "\n")
        return report["exit_code"]
    # The original subprocess uses -I and deliberately does not take this path.
    sys.path.insert(0, str(ROOT / "tools"))
    import pytest_native as runner

    manifest = json.loads(MANIFEST.read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="append", choices=sorted(manifest["suites"]))
    parser.add_argument("--mode", action="append", choices=("python", "jit", "aot"))
    parser.add_argument("--source-cache", type=Path, default=ROOT / "build/pytest-upstream-sources")
    parser.add_argument("--fetch", action="store_true", help="download missing pinned source files and licenses")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build/pytest-upstream")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--compiler", default=shlex.join([sys.executable, str(ROOT / "pystachy.py")]))
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    args.mode = args.mode or ["jit", "aot"]
    names = args.suite or list(manifest["suites"])
    if (not math.isfinite(args.timeout) or args.timeout <= 0 or len(set(names)) != len(names)
            or len(set(args.mode)) != len(args.mode)):
        parser.error("select unique suites/modes and a finite positive timeout")
    if args.list:
        for name in names:
            spec = manifest["suites"][name]
            print(f"{name}: {len(spec['selected'])}/{len(spec['inventory'])} original cases selected")
        return 0
    with runner.lock_work_directory(args.work_dir.resolve()):
        rows = []
        for name in names:
            row = qualify(name, manifest["suites"][name], manifest, args)
            rows.append(row)
            print(f"{name}: {row['state']} ({len(row['selected'])} selected methods)", flush=True)
            if row["state"] != "passed":
                print(row.get("error", ""), file=sys.stderr)
        report = {"schema": 1, "contract": "original unittest -> adapted pytest -> generated CPython -> native",
                  "manifest_sha256": sha256(MANIFEST), "python": sys.version, "suites": rows}
        if args.json:
            runner.write_changed(args.json.resolve(), json.dumps(report, indent=2) + "\n")
    return 0 if rows and all(row["state"] == "passed" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
