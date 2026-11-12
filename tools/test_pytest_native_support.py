"""Behavior and independent pytest-oracle checks for native test helpers."""

import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

import pytest_native_support as support


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
ORACLE_VERSION = "9.2.0"
NATIVE_COMPILER = os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER", "")

# Execute this identical body against upstream pytest and the adapted helpers.
# Side-effect witnesses detect accidental early catches and repeated formatting.
BEHAVIOR = '''
class Child(ValueError):
    pass

problem = Child("needle in value")
with pytest.raises(ValueError, match="nee.*value") as caught:
    raise problem
assert caught.value is problem
assert caught.type is Child
print("subclass and value retained")

with pytest.raises(ValueError) as pending:
    try:
        print(pending.value)
    except AssertionError:
        print("value unavailable before capture")
    try:
        print(pending.type)
    except AssertionError:
        print("type unavailable before capture")
    raise ValueError("captured later")

wrong = TypeError("wrong exception")
try:
    with pytest.raises(ValueError, match="needle"):
        raise wrong
except TypeError as observed:
    assert observed is wrong
    print("wrong exception propagated")

entered = False
try:
    with pytest.raises(ValueError):
        entered = True
except BaseException as error:
    print(type(error).__name__, str(error), entered)

entered = False
try:
    with pytest.raises(ValueError, match="["):
        entered = True
except BaseException as error:
    print(type(error).__name__, entered)

try:
    with pytest.raises(ValueError, match="needle"):
        raise ValueError("different")
except AssertionError:
    print("regex mismatch failed")

try:
    pytest.fail("failure reason")
except BaseException as error:
    print(type(error).__name__, str(error), isinstance(error, Exception))
try:
    pytest.skip("skip reason")
except BaseException as error:
    print(type(error).__name__, str(error), isinstance(error, Exception))
try:
    pytest.xfail("xfail reason")
except BaseException as error:
    print(type(error).__name__, str(error), isinstance(error, Exception))

with pytest.raises(KeyboardInterrupt) as interrupted:
    raise KeyboardInterrupt("expected interrupt")
assert interrupted.type is KeyboardInterrupt
print("explicit BaseException expectation")
'''

EXPECTED_STDOUT = '''subclass and value retained
value unavailable before capture
type unavailable before capture
wrong exception propagated
Failed DID NOT RAISE ValueError True
Failed False
regex mismatch failed
Failed failure reason False
Skipped skip reason False
XFailed xfail reason False
explicit BaseException expectation
'''

NATIVE_REPORT = r'''
import sys
report = pytest.Report(sys.argv[1])
controls = ""
for number in range(32):
    controls += chr(number)
report.record("file::test", "setup", "passed")
report.record("file::test", "call", "failed", controls + '\\"☃😀')
report.record("file::test", "teardown", "passed")
assert report.finish() == 1
print("native report completed")
'''


def python_environment():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(TOOLS)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class RaisesTests(unittest.TestCase):
    def test_supported_behavior_has_the_expected_effects(self):
        ran = subprocess.run([sys.executable, "-c", "import pytest_native_support as pytest\n" + BEHAVIOR],
                             env=python_environment(), capture_output=True, text=True, timeout=30)
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self.assertEqual(ran.stdout, EXPECTED_STDOUT)
        self.assertEqual(ran.stderr, "")

    def test_supported_behavior_matches_pinned_upstream_pytest(self):
        python = os.environ.get("PYSTACHY_PYTEST_ORACLE_PYTHON", sys.executable)
        version = subprocess.run([python, "-c", "import pytest; print(pytest.__version__)"],
                                 capture_output=True, text=True, timeout=30)
        if version.returncode:
            self.skipTest("pytest 9.2.0 is required for the independent oracle")
        self.assertEqual(version.stdout.strip(), ORACLE_VERSION)
        actual = subprocess.run([python, "-c", "import pytest_native_support as pytest\n" + BEHAVIOR],
                                env=python_environment(), capture_output=True, text=True, timeout=30)
        oracle = subprocess.run([python, "-c", "import pytest\n" + BEHAVIOR],
                                env=python_environment(), capture_output=True, text=True, timeout=30)
        self.assertEqual(oracle.returncode, 0, oracle.stdout + oracle.stderr)
        self.assertEqual(actual.returncode, 0, actual.stdout + actual.stderr)
        self.assertEqual(actual.stdout, oracle.stdout)
        self.assertEqual(actual.stderr, oracle.stderr)

    def test_regex_mismatch_formats_the_exception_once(self):
        calls = []

        class Observed(ValueError):
            def __str__(self):
                calls.append("str")
                return "actual message"

        with self.assertRaises(AssertionError):
            with support.raises(ValueError, match="expected"):
                raise Observed()
        self.assertEqual(calls, ["str"])

    def test_no_match_does_not_format_the_exception(self):
        class Unprintable(ValueError):
            def __str__(self):
                raise AssertionError("unexpected formatting")

        problem = Unprintable()
        with support.raises(ValueError) as info:
            raise problem
        self.assertIs(info.value, problem)

    def test_invalid_expected_class_fails_before_the_body(self):
        entered = []
        with self.assertRaises(ValueError):
            with support.raises(int):
                entered.append(True)
        self.assertEqual(entered, [])

    def test_ordinary_exception_handler_does_not_swallow_outcomes(self):
        for function, expected in ((support.fail, support.Failed), (support.skip, support.Skipped),
                                   (support.xfail, support.XFailed)):
            with self.subTest(function=function.__name__), self.assertRaises(expected):
                try:
                    function("reason")
                except Exception:
                    self.fail("application exception handler swallowed the test outcome")


class ReportTests(unittest.TestCase):
    def test_json_string_roundtrip_covers_controls_and_unicode(self):
        strings = ["", '"', "\\", "".join(chr(i) for i in range(32)), "é☃😀", "\ud800", "\udfff"]
        for text in strings:
            with self.subTest(text=repr(text)):
                quoted = support._quote(text)
                self.assertEqual(json.loads(quoted), text)
                self.assertFalse(any(ord(character) < 32 for character in quoted))

    def test_report_is_separate_from_stdout_and_preserves_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.jsonl"
            detail = "".join(chr(i) for i in range(32)) + '\\"☃😀'
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                report = support.Report(str(path))
                print('{"complete":true,"exit_code":0}')
                report.record("file::test[\n]", "call", "failed", detail)
                self.assertEqual(report.finish(), 1)
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(events, [{"nodeid": "file::test[\n]", "phase": "call", "outcome": "failed",
                                       "detail": detail}, {"complete": True, "exit_code": 1}])
            self.assertEqual(output.getvalue(), '{"complete":true,"exit_code":0}\n')

    def test_exit_status_tracks_failures_and_no_tests(self):
        for outcomes, expected in (([], 5), (["passed"], 0), (["skipped"], 0), (["xfailed"], 0),
                                   (["xpassed"], 0), (["failed", "passed"], 1), (["error", "skipped"], 1)):
            with self.subTest(outcomes=outcomes), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "report.jsonl"
                report = support.Report(str(path))
                for index, outcome in enumerate(outcomes):
                    report.record("test_" + str(index), "call", outcome)
                self.assertEqual(report.finish(), expected)
                self.assertEqual(json.loads(path.read_text().splitlines()[-1]),
                                 {"complete": True, "exit_code": expected})

    def test_starting_a_run_removes_old_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.jsonl"
            path.write_text('{"complete":true,"exit_code":0}\n')
            report = support.Report(str(path))
            self.assertEqual(path.read_text(), "")
            report.record("test", "setup", "passed")
            self.assertNotIn("complete", path.read_text())
            report.finish()

    def test_invalid_record_does_not_count_as_a_test(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.jsonl"
            report = support.Report(str(path))
            for phase, outcome in (("unknown", "passed"), ("call", "unknown")):
                with self.subTest(phase=phase, outcome=outcome), self.assertRaises(ValueError):
                    report.record("test", phase, outcome)
            self.assertEqual(path.read_text(), "")
            self.assertEqual(report.finish(), 5)

    def test_completion_and_recording_cannot_continue_after_close(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.jsonl"
            report = support.Report(str(path))
            report.finish()
            previous = path.read_bytes()
            with self.assertRaises(RuntimeError):
                report.finish()
            with self.assertRaises(RuntimeError):
                report.record("test", "call", "passed")
            self.assertEqual(path.read_bytes(), previous)


@unittest.skipUnless(NATIVE_COMPILER, "set PYSTACHY_PYTEST_NATIVE_COMPILER for JIT/AOT helper checks")
class NativeHelperTests(unittest.TestCase):
    def test_jit_aot_and_gc_stress_match_the_cpython_helper(self):
        compiler = shlex.split(NATIVE_COMPILER)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "probe.py"
            source.write_text("import pytest_native_support as pytest\n" + BEHAVIOR + NATIVE_REPORT)
            env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            if os.environ.get("PYSTACHY_LLVM"):
                env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
            # A verified compiler outside the checkout must find this source's lib/.
            env.update(PYSTACHY_PATH=str(TOOLS), PYSTACHY_CACHE=str(directory / "cache"), PYSTACHY_HOME=str(ROOT),
                       PYSTACHY_IRCHECK="1", PYTHONPATH=str(TOOLS), PYTHONDONTWRITEBYTECODE="1")
            expected = subprocess.run([sys.executable, str(source), str(directory / "python.jsonl")],
                                      env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(expected.returncode, 0, expected.stdout + expected.stderr)
            expected_report = (directory / "python.jsonl").read_bytes()
            executable = directory / "probe"
            built = subprocess.run([*compiler, "build", str(source), "-o", str(executable)],
                                   env=env, cwd=ROOT, capture_output=True, text=True, timeout=180)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            for mode in ("jit", "aot"):
                for stress in (False, True):
                    with self.subTest(mode=mode, stress=stress):
                        path = directory / (mode + str(stress) + ".jsonl")
                        options = env.copy()
                        if stress:
                            options["PYSTACHY_GC_STRESS_PROGRAM" if mode == "jit" else "PYSTACHY_GC_STRESS"] = "1"
                        command = ([*compiler, "run", str(source)] if mode == "jit" else [str(executable)])
                        ran = subprocess.run([*command, str(path)], env=options, cwd=ROOT,
                                             capture_output=True, text=True, timeout=120)
                        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                        self.assertEqual(ran.stdout, expected.stdout)
                        self.assertEqual(ran.stderr, expected.stderr)
                        self.assertEqual(path.read_bytes(), expected_report)


if __name__ == "__main__":
    unittest.main()
