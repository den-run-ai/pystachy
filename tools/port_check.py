"""Check two pinned stdlib ports, then run their unedited upstream tests on CPython.

This checks port preservation, not compiled Pystachy compatibility. Only the selected
module is replaced: dependencies such as re and functools remain CPython's. A separate
process per port prevents one port, its imports, or its caches contaminating the other.
"""
import argparse
from collections import Counter
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = "tests/upstream/ports/manifest.json"
STATUSES = {"compiled", "partial", "unmapped", "deviation", "unsupported"}


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate manifest key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def local_file(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"missing or non-local file: {relative}")
    return path


def adaptation_diff(root, module, manifest):
    source = local_file(root, module["source"]).read_bytes().decode("utf-8")
    port = local_file(root, module["port"]).read_bytes().decode("utf-8")
    upstream_path = manifest["files"][module["source"]]["upstream"]
    return "".join(difflib.unified_diff(
        source.splitlines(keepends=True), port.splitlines(keepends=True),
        fromfile=f"a/{upstream_path}", tofile=f"b/{module['port']}"))


def check_sources(root, manifest):
    if manifest["schema"] != 1 or not manifest["modules"] or not manifest["files"]:
        raise ValueError("unsupported or empty port manifest")
    for relative, entry in manifest["files"].items():
        actual = hashlib.sha256(local_file(root, relative).read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {relative}")
    for name, module in manifest["modules"].items():
        if module["source"] not in manifest["files"] or module["test"] not in manifest["files"]:
            raise ValueError(f"{name}: source and test must have pinned SHA-256 hashes")
        expected = local_file(root, module["adaptation"]).read_bytes().decode("utf-8")
        if adaptation_diff(root, module, manifest) != expected:
            raise ValueError(f"{name}: adaptation diff changed; review and refresh {module['adaptation']}")


def check_python(root, manifest):
    pinned = local_file(root, ".python-version").read_text().strip()
    if manifest["upstream"]["python"] != pinned:
        raise ValueError("manifest Python version differs from .python-version")
    if platform.python_implementation() != "CPython" or platform.python_version() != pinned:
        raise ValueError(f"port-check requires CPython {pinned}; running {platform.python_version()}")


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # Execute the checked source bytes, never a stale timestamp-based .pyc.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def assert_origin(module, expected):
    if not getattr(module, "__file__", None) or Path(module.__file__).resolve() != expected.resolve():
        raise ValueError(f"wrong module loaded: {module.__name__}; expected {expected}")
    if sys.modules.get(module.__name__) is not module:
        raise ValueError(f"module binding replaced: {module.__name__}")


def check_bindings(port, upstream_tests, module, root):
    assert_origin(port, local_file(root, module["port"]))
    assert_origin(upstream_tests, local_file(root, module["test"]))
    if not module["bindings"]:
        raise ValueError("empty upstream test bindings")
    for name in module["bindings"]:
        if getattr(upstream_tests, name, None) is not getattr(port, name):
            raise ValueError(f"upstream tests use the wrong {port.__name__}.{name}")
    # Do not turn this into PYTHONPATH=lib: that can silently substitute other ports.
    lib = (root / "lib").resolve()
    for name, imported in list(sys.modules.items()):
        path = getattr(imported, "__file__", None)
        if name != port.__name__ and path and Path(path).resolve().is_relative_to(lib):
            raise ValueError(f"CPython dependency shadowed by another port: {name}")


def cases_in(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from cases_in(test)
        else:
            yield test.id()


def check_cases(root, module, identifiers):
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("empty or duplicate upstream tests")
    if len(identifiers) != module["expected_tests"]:
        raise ValueError(f"upstream test count changed: {len(identifiers)} != {module['expected_tests']}")
    cases = module["cases"]
    if set(identifiers) != set(cases):
        raise ValueError(f"upstream case mapping mismatch: missing={sorted(set(identifiers) - set(cases))}, "
                         f"extra={sorted(set(cases) - set(identifiers))}")
    if not set(module["expected_skips"]).issubset(cases):
        raise ValueError("expected skip is not an upstream case")
    for identifier, entry in cases.items():
        if entry["status"] not in STATUSES or not entry["reason"] or not entry["evidence"]:
            raise ValueError(f"incomplete coverage entry: {identifier}")
        evidence = [local_file(root, path) for path in entry["evidence"]]
        if entry["status"] in {"compiled", "partial"}:
            programs = [path for path in evidence if path.suffix == ".py"
                        and path.parent == (root / "tests").resolve()
                        and f"# {identifier}\n" in path.read_text(encoding="utf-8")]
            if not programs or not all(path.with_suffix(".out").is_file() for path in programs):
                raise ValueError(f"compiled mapping needs upstream ID and differential recording: {identifier}")


def check_result(result, module):
    if result.testsRun != module["expected_tests"]:
        raise ValueError(f"upstream tests run changed: {result.testsRun} != {module['expected_tests']}")
    if not result.wasSuccessful() or result.expectedFailures or result.unexpectedSuccesses:
        raise ValueError("upstream suite has failures, errors, or unexpected expected-failure accounting")
    skipped = {test.id(): reason for test, reason in result.skipped}
    if skipped != module["expected_skips"] or len(skipped) != len(result.skipped):
        raise ValueError(f"upstream skips changed: {skipped!r}")


def run_port(root, name, module):
    port = load_file(name, local_file(root, module["port"]))
    upstream_tests = load_file(f"test_{name}", local_file(root, module["test"]))
    check_bindings(port, upstream_tests, module, root)
    suite = unittest.defaultTestLoader.loadTestsFromModule(upstream_tests)
    identifiers = list(cases_in(suite))
    check_cases(root, module, identifiers)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    check_bindings(port, upstream_tests, module, root)
    check_result(result, module)
    return {"module": name, "mode": "cpython_hosted", "port": module["port"],
            "tests_run": result.testsRun, "passed": result.testsRun - len(result.skipped),
            "skipped": module["expected_skips"], "compiled_mapping": dict(Counter(
                entry["status"] for entry in module["cases"].values()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="write a successful run's machine-readable report")
    parser.add_argument("--module", help=argparse.SUPPRESS)
    args = parser.parse_args()
    manifest = read_json(ROOT / MANIFEST)
    check_python(ROOT, manifest)
    check_sources(ROOT, manifest)
    if args.module:
        print(json.dumps(run_port(ROOT, args.module, manifest["modules"][args.module])))
        return
    results = []
    for name in manifest["modules"]:
        worker = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--module", name],
                                text=True, capture_output=True, timeout=120)
        sys.stderr.write(worker.stderr)
        if worker.returncode:
            raise ValueError(f"{name}: isolated upstream suite failed (exit {worker.returncode})")
        result = json.loads(worker.stdout)
        results.append(result)
        print(f"{name}: CPython-hosted {result['passed']}/{result['tests_run']} passed, "
              f"{len(result['skipped'])} skipped; compiled mapping: {result['compiled_mapping']}")
    report = {"result": "pass", "upstream": manifest["upstream"],
              "python": platform.python_version(), "modules": results}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        sys.exit(f"port-check: {error}")
