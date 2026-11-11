"""Failure controls and original-pytest parity for the generated native runner."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
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
        results = runner.run_suite([first, second], self.root, self.work, "python", [], sys.executable, 10)
        self.assertTrue(all(result.state == "collection-error" for result in results))
        self.assertTrue(all("one source directory" in result.error for result in results))

    def test_discovery_is_deterministic_and_deduplicated(self):
        second = self.source("def test_b(): pass", "nested/test_b.py")
        first = self.source("def test_a(): pass", "a_test.py")
        self.source("raise RuntimeError('not imported')", "helper.py")
        self.source("def test_ignored(): pass", ".cache/test_hidden.py")
        self.assertEqual(runner.discover([self.root, first], self.root), [first, second])

    def test_conftest_never_disappears_from_collection(self):
        path = self.source("def test_a(): pass", "nested/test_a.py")
        self.source("raise RuntimeError('must not execute')", "conftest.py")
        for selected in ([path], [self.root]):
            with self.subTest(selected=selected), self.assertRaisesRegex(CollectionError, "conftest"):
                runner.discover(selected, self.root)

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
    def test_unsupported_test_shapes_fail_explicitly(self):
        sources = {
            "test_class": "class TestThings:\n    def test_one(self): pass\n",
            "async": "async def test_one(): pass\n",
            "custom_decorator": "def custom(f): return f\n@custom\ndef test_one(): pass\n",
            "module_mark": "import pytest\npytestmark = pytest.mark.skip(reason='x')\ndef test_one(): pass\n",
            "plugin": "pytest_plugins = ['something']\ndef test_one(): pass\n",
            "unknown_helper": "import pytest\ndef test_one():\n    pytest.approx(1.0)\n",
            "relative_import": "from . import helper\ndef test_one(): pass\n",
            "imported_test": "from helper import test_imported\n",
            "dynamic_namespace": "globals()['test_dynamic'] = lambda: None\n",
            "file_observation": "def test_one():\n    assert __file__.endswith('test_suite.py')\n",
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
        path = self.source("async def test_one(): pass\n")
        evidence = self.root / "result.json"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = runner.main([str(path), "--root", str(self.root), "--mode", "python",
                                  "--work-dir", str(self.work), "--json", str(evidence)])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(evidence.read_text())["results"][0]["state"], "collection-error")


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
                self.assertIn("exception tuples and non-class values are unsupported", actual.stderr)
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
                self.assertIn(actual.state, {"compile-error", "execution-error"}, actual.events)

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
        unsupported = self.source("async def test_second(): pass\n", "test_second.py")
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


if __name__ == "__main__":
    unittest.main()
