"""Failure controls and original-pytest parity for the generated native runner."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

import pytest_native as runner
from pytest_native_codegen import CollectionError, generate


class TemporarySuite(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pytest-native-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "build"

    def source(self, source, name="test_suite.py"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source))
        return path


class CompilerCommandTests(TemporarySuite):
    def test_relative_compiler_runs_from_another_suite_root_and_preserves_failures(self):
        # This stub tests command launching, without requiring a native compiler.
        compiler = self.source(f"#!{sys.executable}\n" + "import runpy, sys\n"
                               "assert sys.argv[1] == 'run'\n"
                               "sys.argv = sys.argv[2:]\n"
                               "runpy.run_path(sys.argv[0], run_name='__main__')\n", "pystachy.py")
        compiler.chmod(0o755)
        (self.root / "pystachy").symlink_to(compiler.name)
        report = self.root / "report.json"
        for command in (["./pystachy"], [sys.executable, "pystachy.py"]):
            for expected in (1, 2):
                with self.subTest(command=command, expected=expected):
                    path = self.source(f"def test_value(): assert 1 == {expected}\n", "cases/test_suite.py")
                    with contextlib.chdir(self.root), contextlib.redirect_stdout(io.StringIO()), \
                            contextlib.redirect_stderr(io.StringIO()) as error:
                        status = runner.main([str(path), "--root", "cases", "--mode", "jit",
                                              "--compiler", shlex.join(command), "--work-dir", str(self.work),
                                              "--json", str(report)])
                    evidence = json.loads(report.read_text())
                    self.assertEqual(status, expected - 1, error.getvalue())
                    self.assertEqual(evidence["qualification"], "pytest-matched", evidence)
                    self.assertEqual(evidence["results"][0]["state"],
                                     "passed" if expected == 1 else "test-failed")

    def test_missing_compiler_cannot_resolve_to_a_suite_file(self):
        marker = self.root / "wrong-compiler-ran"
        compiler = self.source(f"#!{sys.executable}\n" + "import runpy, sys\n"
                               "from pathlib import Path\n"
                               f"Path({str(marker)!r}).write_text('ran')\n"
                               "sys.argv = sys.argv[2:]\n"
                               "runpy.run_path(sys.argv[0], run_name='__main__')\n",
                               "cases/missing-compiler.py")
        compiler.chmod(0o755)
        path = self.source("def test_value(): assert 1 == 1\n", "cases/test_suite.py")
        report = self.root / "report.json"
        for command in (["./missing-compiler.py"], [sys.executable, "missing-compiler.py"]):
            with self.subTest(command=command):
                marker.unlink(missing_ok=True)
                with contextlib.chdir(self.root), contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()) as error:
                    status = runner.main([str(path), "--root", "cases", "--mode", "jit",
                                          "--compiler", shlex.join(command), "--work-dir", str(self.work),
                                          "--json", str(report)])
                evidence = json.loads(report.read_text())
                self.assertEqual(status, 2, error.getvalue())
                self.assertFalse(marker.exists())
                self.assertEqual(evidence["results"][0]["state"], "execution-error")

    def test_python_stdin_after_option_separator_is_not_a_file(self):
        self.source("raise AssertionError('the dash file must not run')\n", "-")
        with contextlib.chdir(self.root):
            command = runner.compiler_command(shlex.join([sys.executable, "--", "-"]))
            result = subprocess.run(command, input="print('from stdin')\n", text=True,
                                    capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "from stdin\n")

    def test_python_options_modules_and_script_arguments_are_not_paths(self):
        for name in ("python", "pystachy.py", "option.py", "argument.py", "module.py"):
            self.source("", name)
        script = str(self.root / "pystachy.py")
        cases = [
            (["python", "-m", "module.py"], ["python", "-m", "module.py"]),
            (["python", "-mmodule.py"], ["python", "-mmodule.py"]),
            (["python", "-c", "option.py"], ["python", "-c", "option.py"]),
            (["python", "-coption.py"], ["python", "-coption.py"]),
            (["python", "-", "argument.py"], ["python", "-", "argument.py"]),
            (["python", "--unknown", "option.py"], ["python", "--unknown", "option.py"]),
            (["python", "-W", "option.py", "pystachy.py", "argument.py"],
             ["python", "-W", "option.py", script, "argument.py"]),
            (["python", "-X", "option.py", "pystachy.py"], ["python", "-X", "option.py", script]),
            (["python", "--check-hash-based-pycs", "always", "pystachy.py"],
             ["python", "--check-hash-based-pycs", "always", script]),
            (["python", "-B", "-OO", "-Wignore", "-Xdev", "--", "pystachy.py"],
             ["python", "-B", "-OO", "-Wignore", "-Xdev", "--", script]),
            (["pystachy", "--config", "option.py"], ["pystachy", "--config", "option.py"]),
        ]
        with contextlib.chdir(self.root):
            for command, expected in cases:
                with self.subTest(command=command):
                    self.assertEqual(runner.compiler_command(shlex.join(command)), expected)

    def test_quoted_script_and_virtual_environment_executable_keep_their_identity(self):
        python = self.root / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        script = self.source("", "compiler with spaces.py")
        with contextlib.chdir(self.root):
            self.assertEqual(runner.compiler_command(".venv/bin/python 'compiler with spaces.py'"),
                             [str(python), str(script)])


class DiscoveryTests(TemporarySuite):
    def test_same_size_same_timestamp_source_edit_cannot_reuse_stale_tests(self):
        path = self.source("VALUE=1\ndef test_value(): assert VALUE == 1")
        write = runner.write_changed

        def same_timestamp(target, content):
            write(target, content)
            os.utime(target, (1700000000, 1700000000))

        with patch.object(runner, "write_changed", same_timestamp):
            first = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 10)
            path.write_text("VALUE=2\ndef test_value(): assert VALUE == 1\n")
            second = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 10)
        self.assertEqual(first.state, "passed")
        self.assertEqual(second.state, "test-failed")

    def test_concurrent_cli_does_not_overwrite_an_active_workspace(self):
        path = self.source("def test_a(): pass")
        with runner.lock_work_directory(self.work), contextlib.redirect_stderr(io.StringIO()) as error:
            status = runner.main([str(path), "--root", str(self.root), "--mode", "python",
                                  "--work-dir", str(self.work)])
        self.assertEqual(status, 2)
        self.assertIn("work directory is in use", error.getvalue())

    def test_multi_directory_import_search_cannot_create_false_agreement(self):
        first = self.source("def test_a(): pass", "a/test_a.py")
        second = self.source("import helper\ndef test_b(): assert helper.value == 1", "b/test_b.py")
        self.source("value = 1", "a/helper.py")
        self.source("value = 2", "b/helper.py")
        # pytest gives test_b its own directory's helper; one program has one module per name.
        results = runner.run_suite([first, second], self.root, self.work, "python", [], sys.executable, 10)
        self.assertTrue(all(result.state == "collection-error" for result in results))
        self.assertTrue(all("modules named helper are importable from both" in result.error for result in results))

    def test_discovery_is_deterministic_and_deduplicated(self):
        second = self.source("def test_b(): pass", "nested/test_b.py")
        first = self.source("def test_a(): pass", "a_test.py")
        self.source("raise RuntimeError('not imported')", "helper.py")
        self.source("def test_ignored(): pass", ".cache/test_hidden.py")
        self.assertEqual(runner.discover([self.root, first], self.root), [first, second])

    def test_conftest_never_disappears_from_collection(self):
        path = self.source("def test_a(): pass", "nested/test_a.py")
        outer = self.source("raise RuntimeError('runs where pytest runs it')", "conftest.py")
        self.source("VALUE = 1", "other/conftest.py")
        for selected in ([path], [self.root]):
            with self.subTest(selected=selected):
                paths = runner.discover(selected, self.root)
                # The conftest.py above the test applies to it; one beside no test does not.
                self.assertEqual(runner.layout(paths, self.root).conftests, [outer])
        result = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 30)
        self.assertEqual(result.state, "execution-error")
        self.assertIn("runs where pytest runs it", result.stderr)

    def test_pytest_configuration_is_not_silently_ignored(self):
        path = self.source("def test_a(): pass")
        for name, content in (("pytest.ini", "[pytest]\npython_functions = check_*\n"),
                              ("pyproject.toml", "[tool.pytest.ini_options]\n"),
                              ("tox.ini", "[pytest]\n"),
                              ("setup.cfg", "[tool:pytest]\n")):
            with self.subTest(name=name):
                config = self.root / name
                config.write_text(content)
                try:
                    with self.assertRaisesRegex(CollectionError, "configuration"):
                        runner.discover([path], self.root)
                finally:
                    config.unlink()

    def test_invalid_inputs_are_collection_errors(self):
        for path in (self.root / "missing.py", self.source("text", "notes.txt"), self.root.parent):
            with self.subTest(path=path), self.assertRaises(CollectionError):
                runner.discover([path], self.root)


class ReportTests(TemporarySuite):
    nodeid = "test_suite.py::test_one"

    def event(self, phase, outcome="passed", nodeid=None):
        return {"nodeid": nodeid or self.nodeid, "phase": phase, "outcome": outcome, "detail": ""}

    def report(self, events, code=0, complete=True, cases=None):
        path = self.root / "events.jsonl"
        records = list(events)
        if complete:
            records.append({"complete": True, "exit_code": code})
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        return runner.read_report(path, cases or [self.nodeid], code)

    def test_missing_completion_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, "completion"):
            self.report([self.event("setup"), self.event("call"), self.event("teardown")], complete=False)

    def test_missing_report_cannot_pass(self):
        with self.assertRaises(ValueError):
            runner.read_report(self.root / "missing", [self.nodeid], 0)

    def test_missing_call_after_successful_setup_cannot_pass(self):
        with self.assertRaises(ValueError):
            self.report([self.event("setup"), self.event("teardown")])

    def test_call_after_unsuccessful_setup_is_invalid(self):
        for outcome in ("failed", "skipped", "xfailed"):
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                self.report([self.event("setup", outcome), self.event("call"), self.event("teardown")],
                            code=int(outcome == "failed"))

    def test_missing_test_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, "missing test"):
            self.report([self.event("setup"), self.event("call"), self.event("teardown")],
                        cases=[self.nodeid, "test_suite.py::test_two"])

    def test_duplicate_cases_and_phases_are_invalid(self):
        for events, cases in (([self.event("setup"), self.event("call"), self.event("teardown")],
                               [self.nodeid, self.nodeid]),
                              ([self.event("setup"), self.event("call"), self.event("call"),
                                self.event("teardown")], [self.nodeid])):
            with self.subTest(cases=cases, events=events), self.assertRaises(ValueError):
                self.report(events, cases=cases)

    def test_invalid_fields_and_unknown_tests_are_rejected(self):
        invalid = [self.event("setup", nodeid="unknown"), self.event("invalid"),
                   self.event("setup", outcome="unsupported"), {"nodeid": self.nodeid},
                   dict(self.event("setup"), detail=None)]
        for event in invalid:
            with self.subTest(event=event), self.assertRaises(ValueError):
                self.report([event, self.event("call"), self.event("teardown")])

    def test_failed_assertion_cannot_exit_successfully(self):
        with self.assertRaisesRegex(ValueError, "exit status"):
            self.report([self.event("setup"), self.event("call", "failed"), self.event("teardown")])

    def test_setup_failure_is_a_completed_failing_test(self):
        events = [self.event("setup", "error"), self.event("teardown")]
        self.assertEqual(self.report(events, code=1), events)

    def test_completed_empty_module_uses_no_tests_status(self):
        path = self.root / "empty.jsonl"
        path.write_text(json.dumps({"complete": True, "exit_code": 5}) + "\n")
        self.assertEqual(runner.read_report(path, [], 5), [])
        with self.assertRaises(ValueError):
            runner.read_report(path, [], 0)

    def test_comparison_rejects_unexpected_pass(self):
        native = runner.Result("test_suite.py", [self.nodeid],
                               [self.event("setup"), self.event("call"), self.event("teardown")], "passed")
        oracle = {"cases": [self.nodeid], "events": [self.event("setup"), self.event("call", "failed"),
                                                   self.event("teardown")], "exit_code": 1}
        self.assertTrue(runner.compare([native], oracle))

    def test_comparison_rejects_different_phase_and_collection(self):
        native = runner.Result("test_suite.py", [self.nodeid],
                               [self.event("setup", "error"), self.event("teardown")], "test-failed")
        reference = {"cases": [self.nodeid], "events": [self.event("setup"), self.event("call", "failed"),
                                                      self.event("teardown")], "exit_code": 1}
        self.assertTrue(runner.compare([native], reference))
        reference["cases"] = ["test_suite.py::different"]
        self.assertEqual(len(runner.compare([native], reference)), 2)


class CollectionControls(TemporarySuite):
    @unittest.skipUnless(importlib.util.find_spec("pytest"), "real pytest required for independent oracle")
    def test_default_oracle_rejects_imported_autouse_fixture_omission(self):
        self.source("import pytest\n@pytest.fixture(autouse=True)\ndef guard():\n    assert False\n",
                    "helper.py")
        path = self.source("from helper import guard\ndef test_local():\n    pass\n")
        evidence = self.root / "result.json"
        arguments = [str(path), "--root", str(self.root), "--mode", "python",
                     "--work-dir", str(self.work), "--json", str(evidence)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = runner.main(arguments)
        report = json.loads(evidence.read_text())
        self.assertEqual(status, 2)
        self.assertEqual(report["qualification"], "pytest-mismatch")
        self.assertEqual(report["oracle"]["exit_code"], 1)
        self.assertIn("setup/call/teardown outcomes differ from pytest", report["differences"])

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as error:
            status = runner.main([*arguments, "--no-compare"])
        report = json.loads(evidence.read_text())
        self.assertEqual(status, 0)
        self.assertEqual(report["qualification"], "unverified")
        self.assertIsNone(report["oracle"])
        self.assertIn("UNVERIFIED", error.getvalue())

    def test_imported_test_classes_cannot_disappear(self):
        self.source("class TestImported:\n    def test_failure(self):\n        assert False\n", "helper.py")
        self.source("def test_function():\n    assert False\n", "functions.py")
        for statement, name in (("from helper import TestImported", "TestImported"),
                                ("from helper import TestImported as TestAlias", "TestAlias")):
            with self.subTest(statement=statement):
                # pytest collects the class in the module that imports it, under the name bound there.
                path = self.source(statement + "\ndef test_local():\n    pass\n")
                actual = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 10)
                self.assertEqual(actual.state, "test-failed", actual.error)
                self.assertEqual(actual.cases, [f"test_suite.py::{name}::test_failure", "test_suite.py::test_local"])
                if importlib.util.find_spec("pytest"):
                    expected = runner.oracle([path], self.root, self.work / "oracle", sys.executable, 30)
                    self.assertEqual(expected["exit_code"], 1, expected)
                    self.assertEqual(expected["cases"], actual.cases)
        # What the collector cannot read may be a test: a function, or a class of an installed module.
        # Its import is left out and recorded, which fails the run, and pytest's case is missed.
        for statement in ("from functions import test_function", "from installed_elsewhere import TestThing"):
            with self.subTest(statement=statement):
                path = self.source(statement + "\ndef test_local():\n    pass\n")
                actual = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 10)
                self.assertEqual(actual.cases, ["test_suite.py::test_local"])
                self.assertEqual(list(actual.unbound), ["test_suite.py:1: " + statement])
                self.assertIn("imported tests", actual.unbound["test_suite.py:1: " + statement])
                if importlib.util.find_spec("pytest"):
                    expected = runner.oracle([path], self.root, self.work / "oracle", sys.executable, 30)
                    differences = runner.compare([actual], expected)
                    self.assertIn(runner.LEFT_OUT, differences) if "error" not in expected else None
                    self.assertGreater(len(differences), 1 if "error" not in expected else 0, differences)

    def test_dynamic_test_class_aliases_are_rejected(self):
        for statement in ("TestAlias = Helper", "if True:\n    TestAlias = Helper"):
            with self.subTest(statement=statement), self.assertRaisesRegex(CollectionError, "dynamically assigning"):
                generate("class Helper:\n    pass\n" + statement + "\ndef test_local(): pass\n", "test_suite.py")

    def test_unsupported_test_shapes_fail_explicitly(self):
        sources = {
            "test_class_init": "class TestThings:\n    def __init__(self): pass\n    def test_one(self): pass\n",
            "test_class_base": "from helper import Base\nclass TestThings(Base):\n    def test_one(self): pass\n",
            "nested_test_class": "class TestThings:\n    class TestInner:\n        def test_one(self): pass\n",
            "unittest_case": "import unittest\nclass Legacy(unittest.TestCase):\n    def runTest(self): pass\n",
            "xunit_class": "class TestThings:\n    def setup_class(cls): pass\n    def test_one(self): pass\n",
            "async": "async def test_one(): pass\n",
            "custom_decorator": "def custom(f): return f\n@custom\ndef test_one(): pass\n",
            "module_mark": "import pytest\npytestmark = pytest.mark.filterwarnings('error::pkg.Custom')\n"
                           "def test_one(): pass\n",
            "plugin": "pytest_plugins = ['something']\ndef test_one(): pass\n",
            "unknown_helper": "import pytest\ndef test_one():\n    pytest.warns(UserWarning)\n",
            "relative_import": "from . import helper\ndef test_one(): pass\n",
            "imported_test": "from helper import test_imported\n",
            "dynamic_namespace": "globals()['test_dynamic'] = lambda: None\n",
            "file_observation": "__file__ = 'elsewhere.py'\ndef test_one(): pass\n",
        }
        for name, source in sources.items():
            with self.subTest(name=name), self.assertRaises(CollectionError):
                generate(source, "test_suite.py")

    def test_missing_and_cyclic_fixtures_do_not_drop_tests(self):
        sources = ["def test_one(missing): pass\n", """
            import pytest
            @pytest.fixture
            def first(second): return second
            @pytest.fixture
            def second(first): return first
            def test_one(first): pass
        """]
        for source in sources:
            with self.subTest(source=source), self.assertRaises(CollectionError):
                generate(textwrap.dedent(source), "test_suite.py")

    def test_cli_zero_tests_is_not_success(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = runner.main([str(self.root), "--root", str(self.root), "--mode", "python", "--compare"])
        self.assertEqual(status, 5)

    def test_cli_collection_error_is_nonzero(self):
        # A statement of the module itself rejects the module; a test is left out of it.
        for source, state in (("def helper(): pass\nglobals()['test_alias'] = helper\n", "collection-error"),
                              ("async def test_one(): pass\n", "empty")):
            with self.subTest(state=state):
                path = self.source(source)
                evidence = self.root / "result.json"
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    status = runner.main([str(path), "--root", str(self.root), "--mode", "python",
                                          "--work-dir", str(self.work), "--json", str(evidence)])
                result = json.loads(evidence.read_text())["results"][0]
                self.assertEqual(status, 2)
                self.assertEqual(result["state"], state)
                self.assertEqual(list(result["uncollected"]), ["test_suite.py::test_one"] if state == "empty" else [])


LIFECYCLE = '''
import pytest
events: list[str] = ["import"]

@pytest.fixture
def first():
    events.append("first setup")
    value: list[int] = [1]
    yield value
    events.append("first teardown")

@pytest.fixture
def second(first):
    events.append("second setup")
    yield first
    events.append("second teardown")

def test_alias(second, first):
    assert second is first
    second.append(2)
    assert first == [1, 2]

def test_cleanup():
    assert events == ["import", "first setup", "second setup", "second teardown", "first teardown"]
'''

PARTIAL_SETUP = '''
import pytest
events: list[str] = []

@pytest.fixture
def first():
    events.append("setup")
    yield 1
    events.append("cleanup")

@pytest.fixture
def broken(first):
    raise RuntimeError("setup failed")

def test_broken(broken):
    events.append("must not run")

def test_cleanup():
    assert events == ["setup", "cleanup"]
'''

TEARDOWN_FAILURES = '''
import pytest
events: list[str] = []

@pytest.fixture
def first():
    yield 1
    events.append("first")
    raise ValueError("first teardown")

@pytest.fixture
def second():
    yield 2
    events.append("second")
    raise RuntimeError("second teardown")

def test_broken(first, second):
    assert first == second

def test_cleanup():
    assert events == ["second", "first"]
'''

TEARDOWN_OUTCOMES = '''
import pytest

@pytest.fixture
def skip_one():
    yield 1
    pytest.skip("first skip")

@pytest.fixture
def skip_two():
    yield 2
    pytest.skip("second skip")

@pytest.fixture
def xfail_one():
    yield 1
    pytest.xfail("first xfail")

@pytest.fixture
def xfail_two():
    yield 2
    pytest.xfail("second xfail")

def test_all_skips(skip_one, skip_two):
    assert skip_one + skip_two == 3

def test_all_xfails(xfail_one, xfail_two):
    assert xfail_one + xfail_two == 3

def test_mixed(skip_one, xfail_one):
    assert skip_one == xfail_one
'''

OUTCOMES = '''
import pytest

@pytest.mark.skip(reason="unavailable")
def test_skipped():
    assert False

@pytest.mark.skipif(True, reason="conditional")
def test_skipif():
    assert False

@pytest.mark.xfail(reason="known issue")
def test_expected_failure():
    assert False

@pytest.mark.xfail(reason="fixed")
def test_unexpected_pass():
    assert True

@pytest.mark.xfail(reason="strict", strict=True)
def test_strict_pass():
    assert True

def test_runtime_skip():
    pytest.skip("runtime")

def test_runtime_xfail():
    pytest.xfail("runtime")
'''


PYTEST_PARAMETERS = '''
import pytest
from pytest import param as case

@pytest.mark.parametrize("value", [
    case(1, id="é"),
    case(2, id="same"),
    case(3, id="same", marks=pytest.mark.skip(reason="unavailable")),
    case(4, id=None, marks=[pytest.mark.xfail(reason="known failure", strict=True)]),
], ids=["ignored", "ignored", "ignored", "fallback"])
def test_value(value):
    assert value < 4

@pytest.mark.parametrize("value", [case(1, marks=pytest.mark.xfail(reason="strict", strict=True))])
def test_unexpected_pass(value):
    assert value == 1
'''

FIXTURE_ALIASES = '''
import pytest
events: list[str] = []

@pytest.fixture(name="z", autouse=True)
def alpha():
    events.append("alpha")
    return 1

@pytest.fixture(name="a", autouse=True)
def zulu():
    events.append("zulu")
    return 2

@pytest.fixture(name="value")
def make_value():
    values: list[int] = [1]
    yield values
    events.append("teardown")

@pytest.fixture
def same(value):
    return value

def test_alias(value, same, a, z):
    assert events == ["alpha", "zulu"]
    assert value is same
    same.append(a + z)
    assert value == [1, 3]
'''

EMPTY_PARAMETERS = '''
import pytest
shared: list[int] = []

@pytest.mark.parametrize("value", [[], shared], ids=["fresh", "shared"])
def test_list(value: list[int]):
    assert value == []
    value.append(1)

@pytest.mark.parametrize("value,nested", [pytest.param({}, ([[]],), id="empty")])
def test_nested(value: dict[str, int], nested: tuple[list[list[int]]]):
    value["key"] = 2
    nested[0][0].append(value["key"])
    assert nested == ([[2]],)

def test_shared_identity():
    assert shared == [1]
'''


@unittest.skipUnless(importlib.util.find_spec("pytest"), "real pytest required for independent oracle")
class OriginalPytestParity(TemporarySuite):
    def check_parity(self, source, state="passed", mode="python"):
        path = self.source(source)
        compiler = shlex.split(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER", ""))
        actual = runner.run_module(path, self.root, self.work, mode, compiler, sys.executable, 120)
        expected = runner.oracle([path], self.root, self.work / "oracle", sys.executable, 30)
        self.assertEqual(actual.state, state, actual.error + actual.stderr)
        self.assertEqual(runner.compare([actual], expected), [], json.dumps({"actual": actual.events,
                                                                          "expected": expected}, indent=2))
        return actual

    def test_cached_fixtures_alias_and_lifo_cleanup(self):
        self.check_parity(LIFECYCLE)

    def test_named_fixtures_preserve_aliases_and_autouse_order(self):
        self.check_parity(FIXTURE_ALIASES)

    def test_annotation_mutation_cannot_make_a_false_pass(self):
        path = self.source('''
            import pytest
            VALUES = [1]
            def mutate():
                VALUES[0] = 2
                return int
            @pytest.mark.parametrize("value", VALUES)
            def test_value(value: mutate()):
                assert value == 1
        ''')
        # The test receives the changed value, as in pytest, and fails as it does there;
        # the ID read from the source is the stale one, which the comparison reports.
        actual = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 30)
        self.assertEqual(actual.state, "test-failed")
        self.assertEqual(actual.cases, ["test_suite.py::test_value[1]"])
        expected = runner.oracle([path], self.root, self.work / "oracle", sys.executable, 30)
        self.assertEqual(expected.get("exit_code"), 1)
        self.assertEqual(expected["cases"], ["test_suite.py::test_value[2]"])
        self.assertIn("collected test IDs/order differ from pytest", runner.compare([actual], expected))

    def test_nested_shadow_cannot_make_direct_fixture_call_pass(self):
        path = self.source('''
            import pytest
            @pytest.fixture(name="value")
            def make_value(): return 1
            def test_direct():
                def unused():
                    make_value = 0
                    return make_value
                assert make_value() == 1
        ''')
        actual = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 30)
        # The test is left out, not run: nothing of it can pass.
        self.assertEqual((actual.state, actual.cases), ("empty", []))
        self.assertIn("only be requested", actual.uncollected["test_suite.py::test_direct"])
        expected = runner.oracle([path], self.root, self.work / "oracle", sys.executable, 30)
        self.assertEqual(expected.get("exit_code"), 1)
        self.assertEqual(runner.compare([actual], expected), [runner.LEFT_OUT])
        self.assertEqual(runner.outcome_differences([actual], expected),
                         ["test_suite.py::test_direct: pytest failed, native not collected"])

    def test_parameter_set_ids_marks_and_strict_xpass(self):
        self.check_parity(PYTEST_PARAMETERS, "test-failed")

    def test_parameter_set_mutable_values_remain_shared(self):
        self.check_parity('''
            import pytest
            values: list[int] = [1]
            @pytest.mark.parametrize("value,expected", [
                pytest.param(values, 2, id="first"),
                pytest.param(values, 3, id="second"),
            ])
            def test_alias(value, expected):
                assert value is values
                value.append(2)
                assert len(value) == expected
        ''')

    def test_typed_empty_parameter_literals_preserve_shared_aliases(self):
        self.check_parity(EMPTY_PARAMETERS)

    @unittest.skipUnless(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER"), "native compiler opt-in required")
    def test_native_static_pytest_metadata(self):
        for source, state in ((FIXTURE_ALIASES, "passed"), (PYTEST_PARAMETERS, "test-failed"),
                              (EMPTY_PARAMETERS, "passed")):
            with self.subTest(source=source):
                self.check_parity(source, state, mode="jit")

    def test_explicit_parameter_ids_escape_unicode_and_controls(self):
        self.check_parity(r'''
            import pytest
            @pytest.mark.parametrize("value", [1, 2, 3, 4, 5],
                                     ids=["café", "café", "café0", "line\nfeed", "☃"])
            def test_value(value):
                assert value > 0
        ''')

    def test_partial_setup_still_cleans_successful_fixtures(self):
        self.check_parity(PARTIAL_SETUP, "test-failed")

    def test_call_and_multiple_teardown_failures_all_report(self):
        self.check_parity(TEARDOWN_FAILURES, "test-failed")

    def test_multiple_teardown_outcomes_do_not_hide_exception_groups(self):
        self.check_parity(TEARDOWN_OUTCOMES, "test-failed")

    def test_unsupported_raises_shape_cannot_be_caught_or_xfailed(self):
        attempts = [
            "with pytest.raises(TypeError):\n    with pytest.raises(ERRORS):\n        raise ValueError('inner')",
            "with pytest.raises(BaseException):\n    with pytest.raises(ERRORS):\n        raise ValueError('inner')",
            "try:\n    with pytest.raises(ERRORS):\n        raise ValueError('inner')\nexcept BaseException:\n    pass",
            "with pytest.raises(ERRORS):\n    raise ValueError('inner')",
        ]
        for index, body in enumerate(attempts):
            with self.subTest(body=body):
                marker = "@pytest.mark.xfail(reason='expected test failure')\n" if index == 3 else ""
                path = self.source("import pytest\nERRORS = (ValueError,)\n" + marker
                                   + "def test_tuple():\n" + textwrap.indent(body, "    ") + "\n")
                actual = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 30)
                self.assertEqual(actual.state, "execution-error")
                self.assertIn("raises requires an exception class or a literal tuple of classes", actual.stderr)
                expected = runner.oracle([path], self.root, self.work / "oracle", sys.executable, 30)
                self.assertNotIn("error", expected)
                self.assertTrue(runner.compare([actual], expected))

    def test_imported_and_custom_exception_classes_remain_supported(self):
        self.check_parity('''
            import pytest
            from builtins import ValueError as InvalidValue
            class Problem(InvalidValue):
                pass
            def test_class():
                with pytest.raises(InvalidValue):
                    raise Problem("problem")
                with pytest.raises(ValueError):
                    pytest.raises(int)
        ''')

    def test_invalid_exception_class_cannot_satisfy_type_error(self):
        self.check_parity('''
            import pytest
            def test_wrong_error():
                with pytest.raises(TypeError):
                    pytest.raises(int)
        ''', "test-failed")

    def test_skip_xfail_and_strict_unexpected_pass(self):
        self.check_parity(OUTCOMES, "test-failed")

    def test_static_parameters_and_raises(self):
        self.check_parity('''
            import pytest
            @pytest.mark.parametrize("left,right", [(1, 2), (3, 4)], ids=["low", "high"])
            def test_sum(left, right):
                assert left + 1 == right
                with pytest.raises(ValueError, match="problem") as info:
                    raise ValueError("problem")
                assert str(info.value) == "problem"
        ''')

    def test_assertion_keeps_single_evaluation_and_short_circuit(self):
        self.check_parity('''
            events: list[int] = []
            def record(value: int) -> int:
                events.append(value)
                return value
            def test_assert():
                assert record(1) == 1 and record(2) == 2
                assert True or record(3) == 3
                assert events == [1, 2]
        ''')

    def test_mutable_parameter_table_is_shared_between_cases(self):
        self.check_parity('''
            import pytest
            values: list[int] = [1]
            @pytest.mark.parametrize("value,expected", [(values, 2), (values, 3)], ids=["first", "second"])
            def test_alias(value, expected):
                assert value is values
                value.append(2)
                assert len(value) == expected
        ''')

    @unittest.skipUnless(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER"), "native compiler opt-in required")
    def test_native_jit_and_aot_lifecycle(self):
        for mode in ("jit", "aot"):
            with self.subTest(mode=mode):
                self.check_parity(LIFECYCLE, mode=mode)

    @unittest.skipUnless(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER"), "native compiler opt-in required")
    def test_native_exception_class_checks_do_not_create_false_passes(self):
        self.source("class Problem(ValueError):\n    pass\n", "errors_helper.py")
        self.check_parity('''
            import pytest
            from errors_helper import Problem
            class Child(Problem):
                pass
            def test_classes():
                with pytest.raises(Problem):
                    raise Child("problem")
        ''', mode="jit")
        compiler = shlex.split(os.environ["PYSTACHY_PYTEST_NATIVE_COMPILER"])
        for expected in ("int", "ERRORS"):
            with self.subTest(expected=expected):
                path = self.source("import pytest\nERRORS = (ValueError,)\n"
                                   "def test_invalid():\n    with pytest.raises(TypeError):\n"
                                   f"        pytest.raises({expected})\n")
                actual = runner.run_module(path, self.root, self.work, "aot", compiler, sys.executable, 120)
                # The compiler rejects the test, which is left out and reported: no case of it passes.
                self.assertEqual((actual.state, actual.cases, actual.events), ("empty", [], []))
                self.assertEqual(list(actual.uncompiled), ["test_suite.py::test_invalid"])

    @unittest.skipUnless(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER"), "native compiler opt-in required")
    def test_native_failures_do_not_hide_cleanup(self):
        for source in (PARTIAL_SETUP, TEARDOWN_FAILURES, TEARDOWN_OUTCOMES, OUTCOMES):
            with self.subTest(source=source):
                self.check_parity(source, "test-failed", mode="jit")

    @unittest.skipUnless(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER"), "native compiler opt-in required")
    def test_native_any_fixture_keeps_aliases_under_gc_stress(self):
        source = '''
            # pystachy: dynamic-any
            import pytest
            from typing import Any
            @pytest.fixture
            def items() -> list[Any]:
                return [1, "two"]
            def test_payloads(items: list[Any]):
                alias: Any = items
                alias.append("three")
                assert alias is items
                assert items[0] == 1
                assert items[1] == "two"
                assert items[2] == "three"
        '''
        with patch.dict(os.environ, {"PYSTACHY_GC_STRESS_PROGRAM": "1", "PYSTACHY_IRCHECK": "1"}):
            self.check_parity(source, mode="jit")


@unittest.skipUnless(importlib.util.find_spec("pytest"), "real pytest required for independent oracle")
class MultiModuleParity(TemporarySuite):
    def check_suite(self, paths, expected_states, mode="python"):
        compiler = shlex.split(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER", ""))
        actual = runner.run_suite(paths, self.root, self.work, mode, compiler, sys.executable, 120)
        reference = runner.oracle(paths, self.root, self.work / "oracle", sys.executable, 30)
        self.assertEqual([result.state for result in actual], expected_states,
                         "\n".join(result.error + result.stderr for result in actual))
        self.assertEqual(runner.compare(actual, reference), [],
                         json.dumps({"actual": [result.events for result in actual],
                                     "expected": reference}, indent=2))
        return actual

    def shared_helper_suite(self):
        self.source("values: list[int] = []\n", "common_state.py")
        first = self.source('''
            import common_state
            def test_mutates():
                common_state.values.append(1)
        ''', "test_first.py")
        second = self.source('''
            import common_state
            def test_observes_shared_state():
                assert common_state.values == []
        ''', "test_second.py")
        return [first, second]

    def test_shared_helper_state_matches_pytest_failure(self):
        self.check_suite(self.shared_helper_suite(), ["passed", "test-failed"])

    def test_cli_compare_keeps_cross_module_failure(self):
        paths = self.shared_helper_suite()
        evidence = self.root / "result.json"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = runner.main([*(str(path) for path in paths), "--root", str(self.root),
                                "--mode", "python", "--compare", "--work-dir", str(self.work),
                                "--json", str(evidence)])
        result = json.loads(evidence.read_text())
        self.assertEqual(code, 1, result)
        self.assertEqual(result["differences"], [])
        self.assertEqual([module["state"] for module in result["results"]], ["passed", "test-failed"])

    def test_collection_preflight_happens_before_any_execution(self):
        import_marker = self.root / "imported.txt"
        call_marker = self.root / "called.txt"
        first = self.source(f'''
            with open({str(import_marker)!r}, "w") as handle:
                handle.write("import happened")
            def test_first():
                with open({str(call_marker)!r}, "w") as handle:
                    handle.write("test happened")
        ''', "test_first.py")
        unsupported = self.source("def helper(): pass\nglobals()['test_alias'] = helper\n", "test_second.py")
        results = runner.run_suite([first, unsupported], self.root, self.work, "python", [], sys.executable, 30)
        self.assertTrue(any(result.state == "collection-error" for result in results))
        self.assertFalse(import_marker.exists(), "collection preflight ran module initialization")
        self.assertFalse(call_marker.exists(), "collection preflight ran a test")

    def test_zero_test_module_import_failure_is_an_error(self):
        path = self.source("raise RuntimeError('empty module import failed')\n", "test_empty.py")
        results = runner.run_suite([path], self.root, self.work, "python", [], sys.executable, 30)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].state, "execution-error", results[0])
        self.assertIn("empty module import failed", results[0].stderr + results[0].error)

    def test_zero_test_module_imports_before_first_test(self):
        self.source("events: list[str] = []\n", "common_state.py")
        first = self.source('''
            import common_state
            common_state.events.append("first imported")
            def test_collection_finished():
                assert common_state.events == ["first imported", "empty imported"]
        ''', "test_first.py")
        empty = self.source('''
            import common_state
            common_state.events.append("empty imported")
        ''', "test_zempty.py")
        self.check_suite([first, empty], ["passed", "empty"])

    @unittest.skipUnless(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER"), "native compiler opt-in required")
    def test_native_shared_helper_is_one_module(self):
        self.check_suite(self.shared_helper_suite(), ["passed", "test-failed"], mode="jit")



DIALECT = """
import sys

import pytest

LOG: list[str] = []
IS_LINUX = sys.platform.startswith("linux")


@pytest.fixture
def first():
    LOG.append("first")
    yield
    LOG.append("first-down")


@pytest.fixture
def second():
    LOG.append("second")
    yield
    LOG.append("second-down")


@pytest.fixture
def value():
    LOG.append("value")
    return 3


@pytest.mark.usefixtures("first")
@pytest.mark.usefixtures("second")
def test_usefixtures_order(value):
    assert LOG == ["second", "first", "value"]


@pytest.mark.slow
@pytest.mark.network(timeout=5)
def test_labels():
    assert LOG == ["second", "first", "value", "first-down", "second-down"]


@pytest.mark.skipif(sys.version_info < (3, 0), reason="never skipped")
@pytest.mark.skipif(IS_LINUX or not IS_LINUX, reason="always skipped")
def test_runtime_skip():
    assert False


@pytest.mark.skipif(len(LOG) > 100, reason="runs")
def test_runtime_run():
    assert len(LOG) == 5


@pytest.mark.parametrize("n", [1, 2])
@pytest.mark.skipif(len(LOG) > 100, reason="not skipped")
def test_param_skip(n):
    assert n in (1, 2)


if __name__ == "__main__":
    pytest.main([__file__])
"""

OPERANDS = """
log: list[str] = []


def left() -> int:
    log.append("left")
    return 1


def right() -> int:
    log.append("right")
    return 2


def test_order_and_message():
    try:
        assert left() == right()
    except AssertionError as error:
        assert log == ["left", "right"]
        assert "assert 1 == 2" in str(error)
    else:
        assert False


def test_failure_detail():
    numbers = [1, 2]
    assert len(numbers) in (3, 4)
"""


@unittest.skipUnless(importlib.util.find_spec("pytest"), "real pytest required for independent oracle")
class DiagnosticsAndSelection(TemporarySuite):
    check_parity = OriginalPytestParity.check_parity

    def cli(self, *arguments):
        evidence = self.root / "evidence.json"
        evidence.unlink(missing_ok=True)
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            status = runner.main([*map(str, arguments), "--root", str(self.root), "--work-dir", str(self.work),
                                  "--json", str(evidence)])
        report = json.loads(evidence.read_text()) if evidence.exists() else {}
        return status, report, out.getvalue() + err.getvalue()

    def test_failures_name_exceptions_and_comparison_operands(self):
        path = self.source("""
            def add(a: int, b: int) -> int:
                return a + b

            def test_operands():
                result = add(2, 2)
                assert result == add(2, 3)

            def test_missing_key():
                values: dict[str, int] = {}
                assert values["missing"] == 1
        """)
        status, report, output = self.cli(path, "--mode", "python")
        details = {event["nodeid"]: event["detail"] for result in report["results"]
                   for event in result["events"] if event["phase"] == "call"}
        self.assertEqual(status, 1, output)
        self.assertEqual(report["qualification"], "pytest-matched")
        self.assertIn("assert result == add(2, 3)\nassert 4 == 5", details["test_suite.py::test_operands"])
        self.assertEqual(details["test_suite.py::test_missing_key"], "KeyError: 'missing'")
        self.assertIn("pytest (CPython) report:", output)
        self.assertIn("2 failed in", output)

    def test_operands_are_evaluated_once_in_order(self):
        actual = self.check_parity(OPERANDS, "test-failed")
        detail = [event["detail"] for event in actual.events if event["phase"] == "call" and event["outcome"] == "failed"]
        self.assertEqual(len(detail), 1)
        self.assertTrue(detail[0].endswith("assert len(numbers) in (3, 4)\nassert 2 in (3, 4)"), detail)

    def test_mismatches_name_each_test_and_outcome(self):
        path = self.source("""
            import sys

            def test_runner_argv():
                assert sys.argv[0].endswith("__main__.py")
        """)
        status, report, output = self.cli(path, "--mode", "python")
        self.assertEqual(status, 2)
        self.assertEqual(report["mismatches"], ["test_suite.py::test_runner_argv [call]: pytest passed, native failed"])
        self.assertIn("MISMATCH test_suite.py::test_runner_argv [call]", output)

    def test_collection_errors_do_not_run_pytest(self):
        path = self.source("def helper(): pass\nglobals()['test_alias'] = helper\n")
        status, report, output = self.cli(path, "--mode", "python")
        self.assertEqual(status, 2)
        self.assertIsNone(report["oracle"])
        self.assertEqual(report["qualification"], "not-compared")
        self.assertNotIn("differ from pytest", output)

    def test_node_ids_select_cases_in_order_once(self):
        path = self.source("""
            import pytest

            def test_a():
                pass

            def test_b():
                pass

            @pytest.mark.parametrize("x", [1, 2, 3])
            def test_p(x):
                pass
        """)
        status, report, output = self.cli(f"{path}::test_b", f"{path}::test_p[2]", f"{path}::test_b", "--mode", "python")
        self.assertEqual(status, 0, output)
        self.assertEqual(report["results"][0]["cases"], ["test_suite.py::test_b", "test_suite.py::test_p[2]"])
        self.assertEqual(report["oracle"]["cases"], report["results"][0]["cases"])
        for arguments, message in (([f"{path}::test_missing"], "not found: test_suite.py::test_missing"),
                                   ([f"{path}::test_a", str(path)], "give node IDs"),):
            with self.subTest(arguments=arguments):
                status, _, output = self.cli(*arguments, "--mode", "python")
                self.assertEqual(status, 2)
                self.assertIn(message, output)
        other = self.source("def test_c():\n    pass\n", "test_other.py")
        status, _, output = self.cli(f"{path}::test_a", f"{other}::test_c", f"{path}::test_b", "--mode", "python")
        self.assertEqual(status, 2)
        self.assertIn("must be given together", output)

    def test_missing_pytest_is_named(self):
        path = self.source("def test_a():\n    pass\n")
        fake = self.root / "python-without-pytest"
        fake.write_text("#!/bin/sh\necho 'python: No module named pytest' >&2\nexit 1\n")
        fake.chmod(0o755)
        reference = runner.oracle([path], self.root, self.work, str(fake), 30)
        self.assertIn("pytest is not installed for", reference["error"])

    def test_script_guard_labels_usefixtures_and_runtime_skipif(self):
        self.check_parity(DIALECT)

    def test_generated_names_keep_module_identity_and_free_suite(self):
        self.source("VALUE = 1\n", "suite.py")
        self.check_parity("""
            import suite

            class Record:
                pass

            def test_module_identity():
                assert Record.__module__ == "test_suite"
                assert suite.VALUE == 1
        """)

    @unittest.skipUnless(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER"), "native compiler opt-in required")
    def test_native_operands_dialect_and_identity(self):
        actual = self.check_parity(OPERANDS, "test-failed", mode="jit")
        self.assertTrue(actual.assertion_operands)
        self.assertTrue(any(event["detail"].endswith("assert 2 in (3, 4)") for event in actual.events))
        self.check_parity(DIALECT, mode="jit")

    @unittest.skipUnless(os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER"), "native compiler opt-in required")
    def test_native_operand_build_failure_runs_plain_assertions_once(self):
        source = "def test_type():\n    x = 5\n    assert type(x) == int\n"
        for mode in ("jit", "aot"):
            with self.subTest(mode=mode):
                self.work = self.root / f"build-{mode}"
                actual = self.check_parity(source, mode=mode)
                self.assertFalse(actual.assertion_operands)
                self.assertTrue(actual.operand_build_error)
                # The plain choice is kept for the unchanged instrumented code.
                self.assertTrue(any(self.work.glob("*/plain-assertions")))
                again = self.check_parity(source, mode=mode)
                self.assertFalse(again.assertion_operands)
                self.assertEqual(again.operand_build_error, "")


if __name__ == "__main__":
    unittest.main()
