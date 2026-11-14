"""Qualify selected, unchanged upstream json_repair test bodies in three hosts.

The original files run against the pristine upstream library in ordinary pytest.
The selected test functions (including decorators) are copied byte-for-byte into
an explicit adapter. Public imports, an explicitly recorded helper annotation
and the existing dynamic-Any opt-in are the only adaptations.
Every original case ID and phase is compared with adapted pytest and generated
Python/JIT/AOT. This is deliberately separate from the 962-call API replay.
"""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest_native as runner

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/upstream/json_repair"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_environment(imports):
    allowed = {"PYSTACHY_LLVM", "PYSTACHY_CACHE", "PYSTACHY_JOBS"}
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("PYTHON", "PYTEST", "PYSTACHY_")) or key in allowed}
    paths = os.pathsep.join(str(path) for path in imports)
    env.update(PYTHONPATH=paths, PYSTACHY_PATH=paths, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
               PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYSTACHY_HOME=str(ROOT))
    return env


def verify_source(upstream, manifest):
    """Do not let a modified or extra importable source certify the upstream pin."""
    commit = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    if commit != manifest["commit"]:
        raise ValueError("upstream commit does not match the recorded json_repair pin")
    dirty = subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain",
                                     "--untracked-files=all"], text=True)
    if dirty:
        raise ValueError("upstream checkout is modified or contains untracked files")
    expected = dict(manifest["source_sha256"])
    expected.update({"tests/" + name: value for name, value in manifest["test_sha256"].items()})
    expected["LICENSE"] = digest(CORPUS / "LICENSE")
    for name, value in expected.items():
        if digest(upstream / name) != value:
            raise ValueError("upstream source hash mismatch: " + name)
    # Account for package initializers and every other importable checked-in
    # source too; selected original files can import test helpers at import time.
    files = subprocess.check_output(["git", "-C", str(upstream), "ls-files", "*.py"], text=True).splitlines()
    all_sources = {name: digest(upstream / name) for name in files}
    expected_names = set(files)
    extra = [path.relative_to(upstream).as_posix() for path in upstream.rglob("*.py")
             if path.relative_to(upstream).as_posix() not in expected_names]
    if extra:
        raise ValueError("untracked or ignored Python source in upstream checkout: " + str(extra))
    compiled = [path.relative_to(upstream).as_posix() for path in upstream.rglob("*")
                if path.is_file() and path.suffix in {".pyc", ".pyo", ".so", ".pyd"}]
    if compiled:
        raise ValueError("compiled import artifacts in upstream checkout; use a pristine source tree: " + str(compiled))
    return {"commit": commit, "source_sha256": all_sources, "license_sha256": expected["LICENSE"]}


def extract(source, selected, helpers=(), refinements=()):
    """Keep whole function text; assertions, parameters and exception checks stay intact."""
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    if (not selected or len(selected) != len(set(selected))
            or any(name not in functions or not name.startswith("test_") for name in selected)):
        raise ValueError("selection must name unique existing test functions")
    if len(helpers) != len(set(helpers)) or any(name not in functions or name.startswith("test") for name in helpers):
        raise ValueError("helpers must name unique existing non-test functions")
    lines = source.splitlines(keepends=True)
    chunks = []
    hashes = {}
    for name in [*helpers, *selected]:
        node = functions[name]
        start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)]) - 1
        chunk = "".join(lines[start:node.end_lineno])
        hashes[name] = hashlib.sha256(chunk.encode()).hexdigest()
        for refinement in refinements:
            if refinement["function"] == name:
                if name not in helpers:
                    raise ValueError("annotation refinements may only change explicitly selected helpers")
                before, after = refinement["before"], refinement["after"]
                if chunk.count(before) != 1:
                    raise ValueError("helper annotation refinement must match exactly once")
                changed = chunk.replace(before, after)
                old_node, new_node = ast.parse(chunk).body[0], ast.parse(changed).body[0]
                old_body = ast.dump(ast.Module(body=old_node.body, type_ignores=[]))
                new_body = ast.dump(ast.Module(body=new_node.body, type_ignores=[]))
                for function in (old_node, new_node):
                    for argument in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]:
                        argument.annotation = None
                if old_body != new_body or ast.dump(old_node) != ast.dump(new_node):
                    raise ValueError("helper refinement changed more than argument annotations")
                chunk = changed
        chunks.append(chunk)
    if any(refinement["function"] not in helpers for refinement in refinements):
        raise ValueError("refinement names an unselected helper")
    header = ("# pystachy: dynamic-any\n"
              "# Pystachy port: selected upstream functions/decorators are unchanged.\n"
              "# Imports, explicit helper annotations and the existing open-payload opt-in differ.\n"
              "from typing import Any\nimport pytest\nfrom json_repair import loads, repair_json\n\n")
    return header + "\n\n".join(chunks) + "\n", hashes


def pytest_original(upstream, targets, work, python, timeout, collect=False):
    work.mkdir(parents=True, exist_ok=True)
    report = work / "oracle.jsonl"
    report.unlink(missing_ok=True)
    runner.write_changed(work / "_pyn_oracle.py", runner.ORACLE_PLUGIN)
    runner.write_changed(work / "empty.ini", "[pytest]\n")
    env = clean_environment([work, upstream])
    env["PYSTACHY_PYTEST_ORACLE_REPORT"] = str(report)
    command = [python, "-m", "pytest", "-q", "-p", "_pyn_oracle", "-p", "no:cacheprovider",
               "--noconftest", "--rootdir", str(upstream), "-c", str(work / "empty.ini")]
    if collect:
        command.append("--collect-only")
    command.extend(str(upstream / target) for target in targets)
    ran = subprocess.run(command, cwd=upstream, env=env, text=True, capture_output=True, timeout=timeout)
    records = [json.loads(line) for line in report.read_text().splitlines()]
    if not records or records[-1] != {"complete": True, "exit_code": ran.returncode}:
        raise ValueError("original pytest report is incomplete")
    collections = [record["collection"] for record in records if "collection" in record]
    if len(collections) != 1 or ran.returncode != 0:
        raise ValueError("original pytest did not pass/collect: " + ran.stdout + ran.stderr)
    evidence = {"cases": collections[0], "events": [row for row in records if "nodeid" in row],
                "exit_code": ran.returncode, "command": command, "stdout": ran.stdout, "stderr": ran.stderr}
    if not collect:
        require_pass(evidence)
    return evidence


def require_pass(evidence):
    cases = evidence["cases"]
    if not cases or len(cases) != len(set(cases)) or evidence["exit_code"] != 0:
        raise ValueError("empty/duplicate collection or failing process")
    expected = [(case, phase, "passed") for case in cases for phase in ("setup", "call", "teardown")]
    actual = [(event["nodeid"], event["phase"], event["outcome"]) for event in evidence["events"]]
    if actual != expected:
        raise ValueError("every selected upstream case and phase must execute and pass")


def remap(evidence):
    """Only the explicitly relocated tests/ prefix may change test identity."""
    def nodeid(value):
        if not value.startswith("tests/"):
            raise ValueError("unexpected original test path: " + value)
        return value[len("tests/"):]
    return {**evidence, "cases": [nodeid(case) for case in evidence["cases"]],
            "events": [{**event, "nodeid": nodeid(event["nodeid"])} for event in evidence["events"]]}


def qualify(args, evidence=None):
    if evidence is None:
        evidence = {"state": "error"}
    upstream, work = args.upstream.resolve(), args.work_dir.resolve()
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    selection = json.loads((CORPUS / "pytest-selection.json").read_text())
    if selection["upstream_commit"] != manifest["commit"]:
        raise ValueError("selection and source pins differ")
    source = verify_source(upstream, manifest)
    versions = subprocess.check_output([args.python, "-c", "import json,platform,pytest; "
                                       "print(json.dumps({'python':platform.python_version(),'pytest':pytest.__version__}))"],
                                      text=True, env=clean_environment(()), cwd=ROOT).strip()
    evidence["versions"] = json.loads(versions)
    pinned = {"python": (ROOT / ".python-version").read_text().strip(), "pytest": "9.2.0"}
    if evidence["versions"] != pinned:
        raise ValueError("upstream qualification requires pinned Python/pytest: " + str(pinned))
    selected = selection["selected"]
    adapted = work / "adapted"
    adapted.mkdir(parents=True, exist_ok=True)
    expected_paths = {adapted / name for name in selected}
    if set(adapted.glob("*.py")) - expected_paths:
        raise ValueError("stale adapter modules; choose a fresh --work-dir")
    functions = {}
    for name, names in selected.items():
        text, hashes = extract((upstream / "tests" / name).read_text(), names,
                               selection.get("helpers", {}).get(name, ()),
                               selection.get("helper_annotation_refinements", {}).get(name, ()))
        runner.write_changed(adapted / name, text)
        functions[name] = hashes
    runner.write_changed(adapted / "LICENSE", (upstream / "LICENSE").read_text())
    full = pytest_original(upstream, ["tests/" + name for name in selected], work / "inventory",
                           args.python, args.timeout, collect=True)
    targets = ["tests/" + name + "::" + test for name, names in selected.items() for test in names]
    original = pytest_original(upstream, targets, work / "original", args.python, args.timeout)
    if any(case not in full["cases"] for case in original["cases"]):
        raise ValueError("selected original case is missing from complete inventory")
    unselected = [case for case in full["cases"] if case not in original["cases"]]
    modules = sorted(path.relative_to(upstream).as_posix()
                     for path in (upstream / "tests").rglob("test_*.py"))
    selected_modules = ["tests/" + name for name in selected]
    # Every consumed source and the exact selected assertion bodies are recorded.
    evidence.update({"schema_version": 1, "source": source, "selection": selection,
                "function_sha256": functions, "original": original,
                "inventory_scope": "Complete pytest case inventory of the selected five source modules only",
                "source_module_inventory": modules,
                "excluded_modules": [{"path": name, "reason": "Outside selected source-module scope; no case-count claim. "
                                       + selection["excluded_scope"]}
                                     for name in modules if name not in selected_modules],
                "inventory": full["cases"],
                "exclusions": [{"nodeid": case, "reason": selection["excluded_scope"]} for case in unselected],
                "adapted_source_sha256": {name: digest(adapted / name) for name in selected},
                "port_sha256": {path.relative_to(ROOT).as_posix(): digest(path)
                                for path in sorted((ROOT / "ports").rglob("*.py"))}, "modes": []})
    expected = remap(original)
    for mode in args.mode:
        report = work / mode / "result.json"
        report.unlink(missing_ok=True)
        command = [args.python, str(ROOT / "tools/pytest_native.py"), str(adapted),
                   "--root", str(adapted), "--work-dir", str(work / mode),
                   "--mode", mode, "--compare", "--compiler", args.compiler,
                   "--python", args.python, "--timeout", str(args.timeout), "--json", str(report)]
        ran = subprocess.run(command, cwd=ROOT, env=clean_environment([ROOT / "ports"]),
                             text=True, capture_output=True, timeout=3 * args.timeout + 30)
        row = json.loads(report.read_text())
        evidence["modes"].append({"mode": mode, "command": command, "evidence": row})
        results = [runner.Result(**result) for result in row["results"]]
        if ran.returncode != 0 or row["exit_code"] != 0 or row["differences"] or not row["oracle"]:
            raise ValueError(mode + " qualification failed: " + ran.stdout + ran.stderr)
        require_pass(row["oracle"])
        flat = {"cases": [case for result in results for case in result.cases],
                "events": [event for result in results for event in result.events], "exit_code": 0}
        require_pass(flat)
        differences = runner.compare(results, expected) + runner.compare(results, row["oracle"])
        if differences:
            raise ValueError(mode + ": " + "; ".join(differences))
        print(f"json_repair/{mode}: {len(flat['cases'])} original/adapted/generated cases match", flush=True)
    evidence["state"] = "passed"
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path, help="pristine pinned upstream git checkout")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--compiler", default=shlex.join([sys.executable, str(ROOT / "pystachy.py")]))
    parser.add_argument("--mode", action="append", choices=("python", "jit", "aot"))
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build/pytest-upstream-json")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args(argv)
    args.compiler = shlex.join(runner.compiler_command(args.compiler))
    args.mode = args.mode or ["python", "jit", "aot"]
    if len(args.mode) != len(set(args.mode)) or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("modes must be unique and timeout finite and positive")
    evidence = {"state": "error"}
    try:
        with runner.lock_work_directory(args.work_dir.resolve()):
            evidence = qualify(args, evidence)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        evidence["error"] = str(error)
        print(str(error), file=sys.stderr)
    if args.json:
        runner.write_changed(args.json.resolve(), json.dumps(evidence, indent=2) + "\n")
    return 0 if evidence["state"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
