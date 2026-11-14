"""Original-pytest parity and rejections for test classes, scopes, params and helpers."""
import contextlib
import importlib.util
import io
import json
import os
import shlex
import sys
import textwrap
import unittest
from unittest.mock import patch

import pytest_native as runner
from pytest_native_codegen import CollectionError, GeneratedModule, generate, generate_conftest, original_line
from test_pytest_native import TemporarySuite

NATIVE = os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER", "")

CLASSES = '''
import pytest

LOG: list[str] = []


@pytest.fixture
def base() -> int:
    return 10


@pytest.fixture(autouse=True)
def note():
    LOG.append("up")
    yield
    LOG.append("down")


def test_before():
    assert LOG == ["up"]


@pytest.mark.parametrize("scale", [1, 2])
class TestMath:
    limit = 30
    test_values = [1, 2]

    def helper(self, value: int) -> int:
        return value + 1

    def test_add(self, base, scale):
        assert self.helper(base) * scale <= self.limit

    @pytest.mark.parametrize("extra", [5, 50], ids=["small", "large"])
    def test_extra(self, base, extra, scale):
        assert base * scale + extra < 60

    @pytest.mark.skip(reason="not yet")
    def test_skipped(self, scale):
        assert False

    @pytest.mark.xfail(reason="known")
    def test_expected(self, scale):
        assert scale == 3


@pytest.mark.skip(reason="whole class")
class TestSkipped:
    def test_one(self):
        assert False


@pytest.mark.usefixtures("doubled")
@pytest.mark.xfail(reason="class wide")
class TestMarked:
    @pytest.fixture
    def doubled(self, base):
        LOG.append("doubled")
        return base * 2

    @pytest.fixture(autouse=True)
    def around(self):
        LOG.append("class up")
        yield
        LOG.append("class down")

    def test_fails(self, doubled):
        assert doubled == 21

    def test_order(self):
        assert LOG[-3:] == ["up", "class up", "doubled"]

    @pytest.mark.skipif(LOG == ["never"], reason="evaluated at import")
    def test_condition(self):
        assert True


class TestEmpty:
    pass


class Helper:
    def test_me(self) -> int:
        return 5


def test_after():
    def tester(value: int) -> int:
        return value + 1
    assert tester(1) == 2 and Helper().test_me() == 5
    assert LOG[-3:] == ["class down", "down", "up"]
'''

ASSERTIONS = '''
import pytest
from pytest import approx


class Custom(Exception):
    pass


class Value:
    def __repr__(self) -> str:
        raise ValueError("bad repr")

    def __eq__(self, other: object) -> bool:
        return False


def test_approx_forms():
    assert 0.1 + 0.2 == pytest.approx(0.3)
    assert 0.1 + 0.2 != pytest.approx(0.4)
    assert 5 == approx(5.1, abs=0.2)
    assert 5 != approx(5.1)
    assert 1000.0 == approx(1001, rel=1e-2)
    assert 100 == approx(101, rel=0.001, abs=2)
    assert 3 == approx(3)
    assert pytest.approx(0.3) == 0.1 + 0.2
    assert not (2.0 == approx(3))
    assert float("nan") == approx(float("nan"), nan_ok=True)
    assert float("nan") != approx(float("nan"))
    assert float("inf") == approx(float("inf"))
    assert 1e300 != approx(float("inf"))
    assert [2.5000001 == approx(2.5), 2.6 == approx(2.5)] == [True, False]


def test_approx_compares_large_ints_exactly():
    # (Two ints that one float holds: 2**53 and 2**53 + 1.)
    assert 9007199254740992 != pytest.approx(9007199254740993, rel=0, abs=0)
    assert 9007199254740993 == pytest.approx(9007199254740993, rel=0, abs=0)
    assert 9007199254740992 == pytest.approx(9007199254740993, rel=0, abs=1)
    assert 9007199254740990 != pytest.approx(9007199254740993, rel=0, abs=2.5)
    assert 9007199254740991 == pytest.approx(9007199254740993, rel=0, abs=2.5)
    assert 9007199254740992 == pytest.approx(9007199254740993)
    assert 9007199254740992.0 == pytest.approx(9007199254740993, rel=0, abs=0)


def test_approx_large_int_failure():
    assert 9007199254740992 == pytest.approx(9007199254740993, rel=0, abs=0)


def test_approx_failure():
    assert 1.0 == pytest.approx(1.1)


def test_exact_match_never_reads_a_negative_tolerance():
    with pytest.raises(ValueError):
        assert 1 == pytest.approx(1, abs=-1.0)


def test_negative_relative_tolerance():
    with pytest.raises(ValueError):
        assert 1 == pytest.approx(2, rel=-1.0)


def test_raises_tuple():
    with pytest.raises((KeyError, ValueError)) as info:
        int("x")
    assert info.type is ValueError
    assert info.typename == "ValueError"
    assert info.match("invalid literal")


def test_raises_tuple_custom():
    with pytest.raises((Custom, KeyError), match="bo+m"):
        raise Custom("boom")


def test_raises_tuple_miss():
    with pytest.raises((KeyError, Custom)):
        int("x")


def test_match_method_fails():
    with pytest.raises(ValueError) as info:
        int("x")
    info.match("no such text")


def test_failing_repr_keeps_the_assertion():
    with pytest.raises(AssertionError):
        assert Value() == 1


def test_failing_repr_fails_as_an_assertion():
    assert Value() == 1


@pytest.mark.xfail(raises=ZeroDivisionError)
def test_xfail_raises():
    1 // 0


@pytest.mark.xfail(raises=(KeyError, ZeroDivisionError), reason="either")
def test_xfail_raises_tuple():
    1 // 0


@pytest.mark.xfail(raises=KeyError)
def test_xfail_raises_other():
    1 // 0


@pytest.mark.xfail(raises=Custom, strict=True)
def test_xfail_raises_strict_pass():
    pass


@pytest.fixture
def broken():
    raise Custom("setup")


@pytest.fixture
def late():
    yield 1
    raise Custom("teardown")


@pytest.mark.xfail(raises=Custom)
def test_xfail_raises_setup(broken):
    pass


@pytest.mark.xfail(raises=KeyError)
def test_xfail_raises_setup_other(broken):
    pass


@pytest.mark.xfail(raises=Custom)
def test_xfail_raises_teardown(late):
    pass


@pytest.mark.xfail(raises=KeyError)
def test_xfail_raises_teardown_other(late):
    pass


@pytest.mark.parametrize("n", [pytest.param(0, marks=pytest.mark.xfail(raises=ZeroDivisionError)), 1])
def test_param_raises(n):
    assert 1 // n == 1
'''

TYPED_VALUE = '''
import pytest


class HttpError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class NotFound(HttpError):
    pass


def fetch(code: int) -> str:
    if code == 404:
        raise NotFound(code, "not found")
    if code >= 400:
        raise HttpError(code, "failed")
    return "body"


def test_code():
    with pytest.raises(HttpError) as info:
        fetch(500)
    assert info.value.code == 500
    assert str(info.value) == "failed"
    assert info.type is HttpError
    assert info.typename == "HttpError"


def test_subclass_and_match():
    with pytest.raises(HttpError, match="not f") as caught:
        fetch(404)
    assert caught.value.code == 404
    assert caught.type is NotFound
    assert caught.match("found$")


def test_did_not_raise():
    with pytest.raises(HttpError) as info:
        fetch(200)
    assert info.value.code == 0


def test_other_exception_propagates():
    with pytest.raises(HttpError) as info:
        int("x")
    assert info.value.code == 0


def test_match_fails():
    with pytest.raises(HttpError, match="nope") as info:
        fetch(500)
    assert info.value.code == 500


@pytest.mark.parametrize("code", [400, 404])
def test_loop(code):
    for attempt in range(2):
        with pytest.raises(HttpError) as info:
            fetch(code)
        assert info.value.code == code + attempt * 0


def test_two_names():
    with pytest.raises(HttpError) as first:
        fetch(400)
    with pytest.raises(NotFound) as second:
        fetch(404)
    assert first.value.code + second.value.code == 804


def test_reused_name_keeps_the_context_manager():
    with pytest.raises(HttpError) as info:
        fetch(400)
    assert str(info.value) == "failed"
    with pytest.raises(NotFound) as info:
        fetch(404)
    assert str(info.value) == "not found"


def test_match_none_is_no_pattern():
    with pytest.raises(HttpError, match=None) as info:
        fetch(500)
    assert info.value.code == 500
'''

FIXTURE_PARAMS = '''
import pytest


@pytest.fixture(params=["x", "y"])
def first(request):
    return request.param


@pytest.fixture(params=[1, 2], ids=["one", "two"])
def second(request, first):
    yield first * request.param
    assert request.param in (1, 2)


@pytest.fixture(autouse=True, params=["on", "off"])
def switch(request):
    return request.param


@pytest.fixture(params=[10, 20])
def counted():
    return 0


@pytest.mark.parametrize("extra", ["E"])
class TestMatrix:
    @pytest.fixture(params=[3, 4])
    def local(self, request):
        return request.param

    @pytest.mark.parametrize("more", [0, 1])
    def test_all(self, second, more, extra, switch):
        assert second in ("x", "y", "xx", "yy")

    def test_local(self, local, first, extra):
        assert local in (3, 4) and first in "xy"


def test_function(second, switch, counted):
    assert len(second) in (1, 2) and counted == 0


@pytest.mark.parametrize("first", ["z"])
def test_direct_parameter_replaces_the_fixture(second, first):
    assert second in ("z", "zz")
'''

SCOPES = '''
import pytest

LOG: list[str] = []


@pytest.fixture(scope="session", autouse=True)
def final_check():
    yield
    # Scopes end innermost first, each in the reverse of its setup order.
    assert LOG[-4:] == ["class-", "module-", "auto-", "session-"], LOG


@pytest.fixture(scope="session")
def session_value():
    LOG.append("session+")
    yield [1]
    LOG.append("session-")


@pytest.fixture(scope="module")
def module_value(session_value):
    LOG.append("module+")
    yield session_value + [2]
    LOG.append("module-")


@pytest.fixture(scope="module")
def plain_module():
    LOG.append("plain+")
    return {"k": 1}


@pytest.fixture(scope="class")
def class_value(module_value):
    LOG.append("class+")
    yield len(module_value)
    LOG.append("class-")


@pytest.fixture(scope="module", autouse=True)
def auto_module():
    LOG.append("auto+")
    yield
    LOG.append("auto-")


@pytest.fixture
def each(class_value):
    LOG.append("each+")
    yield class_value + 1
    LOG.append("each-")


def test_first(each):
    assert each == 3
    assert LOG == ["session+", "auto+", "module+", "class+", "each+"]


def test_second(module_value, plain_module):
    assert module_value == [1, 2] and plain_module == {"k": 1}
    # A class-scoped fixture ends with each test outside a class.
    assert LOG == ["session+", "auto+", "module+", "class+", "each+", "each-", "class-", "plain+"]


class TestOne:
    def test_a(self, each):
        assert LOG[-2:] == ["class+", "each+"]

    def test_b(self, each, plain_module):
        assert LOG[-3:] == ["each+", "each-", "each+"]


class TestTwo:
    def test_c(self, class_value):
        assert LOG[-3:] == ["each-", "class-", "class+"]


def test_last():
    assert LOG[-2:] == ["class+", "class-"]
    assert LOG.count("module+") == 1 and LOG.count("session+") == 1 and LOG.count("plain+") == 1
'''

SCOPE_FAILURES = '''
import pytest

CALLS: list[str] = []


@pytest.fixture(scope="module")
def broken():
    CALLS.append("broken")
    raise ValueError("no database")


@pytest.fixture(scope="module")
def skipping():
    CALLS.append("skipping")
    pytest.skip("not available")


@pytest.fixture(scope="module")
def late_error():
    yield 1
    raise RuntimeError("module teardown")


@pytest.fixture(scope="class")
def class_late():
    yield 2
    raise RuntimeError("class teardown")


@pytest.fixture(scope="module")
def unused_later():
    CALLS.append("never")
    return 1


def test_broken_one(broken):
    assert False


def test_broken_two(broken):
    assert False


def test_skipping_one(skipping):
    assert False


def test_skipping_two(skipping):
    assert False


def test_setup_ran_once():
    assert CALLS == ["broken", "skipping"]


class TestLate:
    def test_uses(self, class_late, late_error):
        assert class_late + late_error == 3

    def test_last_in_class(self):
        assert True


@pytest.mark.xfail(run=False, reason="not run")
def test_not_run(unused_later):
    assert False


@pytest.mark.skip(reason="the module ends here")
def test_skipped_last():
    assert False
'''

BUILTIN = '''
import os

import pytest


class TestA:
    def test_same(self, tmp_path):
        assert tmp_path.name == "test_same0"


class TestB:
    def test_same(self, tmp_path):
        assert tmp_path.name == "test_same1" and list(tmp_path.iterdir()) == []


def test_tmp_path(tmp_path):
    target = tmp_path / "note.txt"
    target.write_text("hello")
    assert target.read_text() == "hello" and tmp_path.is_dir()


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "data").mkdir()
    return tmp_path / "data"


@pytest.mark.parametrize("name", ["a b", "longlonglonglonglonglonglonglonglonglong"])
def test_workspace(workspace, name):
    (workspace / "item").write_text(name)
    assert sorted(item.name for item in workspace.iterdir()) == ["item"]
    assert workspace.parent.name.startswith("test_workspace_") and len(workspace.parent.name) <= 31


def test_setenv(monkeypatch):
    monkeypatch.setenv("PYN_PROBE", "one")
    assert os.environ["PYN_PROBE"] == "one"
    monkeypatch.setenv("PYN_PROBE", "two", prepend=":")
    assert os.environ["PYN_PROBE"] == "two:one"
    monkeypatch.delenv("PYN_PROBE")
    monkeypatch.delenv("PYN_PROBE", raising=False)
    with pytest.raises(KeyError):
        monkeypatch.delenv("PYN_PROBE")


def test_env_restored():
    assert os.environ.get("PYN_PROBE") is None


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("PYN_MODE", "test")
    return os.environ["PYN_MODE"]


def test_fixture_env(configured):
    assert configured == "test" and os.environ["PYN_MODE"] == "test"


def test_fixture_env_restored():
    assert os.environ.get("PYN_MODE") is None
'''

NAMES = '''
import pytest

import test_helpers

test_cases = [(1, 2), (2, 3)]
TestData = ("a", "b")


@pytest.mark.parametrize("left,right", test_cases)
def test_increment(left, right):
    assert test_helpers.increment(left) == right


def test_data():
    assert TestData == ("a", "b")
'''

CONFTEST = '''
import pytest

EVENTS: list[str] = []


@pytest.fixture(autouse=True)
def auto():
    EVENTS.append("auto")


@pytest.fixture
def base_value() -> int:
    return 41


@pytest.fixture(params=["sweet", "sour"])
def flavour(request):
    return request.param


@pytest.fixture(scope="module")
def shared_list() -> list[int]:
    return []


@pytest.fixture(scope="session")
def session_counter():
    EVENTS.append("session")
    yield [EVENTS.count("session")]
    EVENTS.append("session end")
    raise RuntimeError("session teardown")
'''

CONFTEST_FIRST = '''
import pytest

import conftest


def test_shared(shared_list):
    shared_list.append(1)
    assert conftest.EVENTS[0] == "auto"


def test_shared_again(shared_list, session_counter):
    assert shared_list == [1] and session_counter == [1]


@pytest.fixture
def local(base_value):
    return base_value + 1


def test_local(local, flavour):
    assert local == 42 and flavour in ("sweet", "sour")


class TestInClass:
    def test_base(self, base_value):
        assert base_value == 41
'''

CONFTEST_SECOND = '''
import conftest


def test_module_scope_is_new(shared_list, session_counter):
    assert shared_list == [] and session_counter == [1]
    assert "session end" not in conftest.EVENTS


def test_last_ends_the_session():
    assert conftest.EVENTS.count("session") == 1
'''

SELECTION = '''
import pytest

LOG: list[str] = []


@pytest.fixture(scope="class")
def grouped():
    LOG.append("grouped+")
    yield len(LOG)
    LOG.append("grouped-")


@pytest.fixture(scope="module")
def whole():
    LOG.append("whole+")
    yield 1
    LOG.append("whole-")


class TestA:
    def test_one(self, grouped, whole):
        LOG.append("one")

    @pytest.mark.parametrize("n", [1, 2])
    def test_two(self, grouped, n):
        LOG.append("two" + str(n))


def test_plain(whole):
    LOG.append("plain")


class TestB:
    def test_three(self, grouped):
        LOG.append("three")

    def test_log(self):
        assert LOG == EXPECTED
'''

# name: (source, state); every suite matches pytest phase by phase.
SUITES = {
    "classes": (CLASSES, "test-failed"),
    "assertions": (ASSERTIONS, "test-failed"),
    "typed_value": (TYPED_VALUE, "test-failed"),
    "fixture_params": (FIXTURE_PARAMS, "passed"),
    "scopes": (SCOPES, "passed"),
    "scope_failures": (SCOPE_FAILURES, "test-failed"),
    "builtin": (BUILTIN, "passed"),
    "names": (NAMES, "passed"),
}


@unittest.skipUnless(importlib.util.find_spec("pytest"), "real pytest required for independent oracle")
class FormParity(TemporarySuite):
    def check(self, name, mode="python"):
        source, state = SUITES[name]
        self.source("def increment(value: int) -> int:\n    return value + 1\n", "test_helpers.py")
        path = self.source(source)
        actual = runner.run_module(path, self.root, self.work / name / mode, mode, shlex.split(NATIVE),
                                   sys.executable, 180)
        expected = runner.oracle([path], self.root, self.work / "oracle", sys.executable, 60)
        self.assertEqual(actual.state, state, actual.error + actual.stderr)
        self.assertEqual(runner.compare([actual], expected), [], json.dumps(
            runner.outcome_differences([actual], expected), indent=2))
        return actual, expected

    def outcomes(self, actual):
        return {(event["nodeid"].split("::", 1)[1], event["phase"]): event["outcome"] for event in actual.events}

    def test_python_parity(self):
        for name in SUITES:
            with self.subTest(suite=name):
                self.check(name)

    def test_class_cases_and_marks(self):
        actual, expected = self.check("classes")
        self.assertEqual(len(expected["cases"]), 16)
        self.assertIn("test_suite.py::TestMath::test_extra[large-2]", actual.cases)
        outcomes = self.outcomes(actual)
        self.assertEqual(outcomes["TestMath::test_extra[large-2]", "call"], "failed")
        self.assertEqual(outcomes["TestMath::test_skipped[1]", "setup"], "skipped")
        self.assertEqual(outcomes["TestSkipped::test_one", "setup"], "skipped")
        self.assertEqual(outcomes["TestMarked::test_fails", "call"], "xfailed")
        self.assertEqual(outcomes["TestMarked::test_order", "call"], "xpassed")

    def test_helpers_report_failures_not_false_passes(self):
        actual, _ = self.check("assertions")
        outcomes = self.outcomes(actual)
        failed = {name for (name, phase), outcome in outcomes.items() if outcome in {"failed", "error"}}
        self.assertEqual(failed, {
            "test_approx_failure", "test_approx_large_int_failure",
            "test_exact_match_never_reads_a_negative_tolerance", "test_raises_tuple_miss",
            "test_match_method_fails", "test_failing_repr_fails_as_an_assertion", "test_xfail_raises_other",
            "test_xfail_raises_strict_pass", "test_xfail_raises_setup_other", "test_xfail_raises_teardown_other"})
        self.assertEqual(outcomes["test_xfail_raises_setup", "setup"], "xfailed")
        self.assertEqual(outcomes["test_xfail_raises_teardown", "teardown"], "xfailed")
        self.assertEqual(outcomes["test_param_raises[0]", "call"], "xfailed")
        details = {event["nodeid"].split("::")[1]: event["detail"] for event in actual.events
                   if event["outcome"] == "failed"}
        self.assertTrue(details["test_failing_repr_fails_as_an_assertion"].startswith("AssertionError: "))
        self.assertIn("raised in repr()", details["test_failing_repr_fails_as_an_assertion"])
        self.assertTrue(details["test_approx_failure"].endswith("assert 1.0 == 1.1 ± 1.1e-06"), details)
        self.assertTrue(details["test_approx_large_int_failure"].endswith(
            "assert 9007199254740992 == 9007199254740993 ± 0.0"), details)

    def test_typed_value_expands_only_where_it_is_safe(self):
        actual, _ = self.check("typed_value")
        outcomes = self.outcomes(actual)
        self.assertEqual({name for (name, phase), outcome in outcomes.items() if outcome == "failed"},
                         {"test_did_not_raise", "test_other_exception_propagates", "test_match_fails"})
        source = generate(textwrap.dedent(TYPED_VALUE), "test_suite.py").source
        self.assertIn("except HttpError as _pyn_caught_", source)
        # A name bound by two blocks cannot become one typed variable.
        self.assertIn("with pytest.raises(NotFound) as info:", source)
        # pytest.raises keeps the class it was given; a handler would read the name again
        # after the body, so a class the function binds keeps the context manager.
        rebound = self.source("""
            import pytest
            class Problem(Exception):
                def __init__(self, code: int) -> None:
                    super().__init__("problem")
                    self.code = code
            def test_local_class_is_read_once():
                expected = Problem
                with pytest.raises(expected) as info:
                    expected = TypeError
                    raise Problem(7)
                assert info.value.code == 7
            def test_argument(expected=Problem):
                with pytest.raises(expected) as info:
                    raise Problem(8)
                assert info.value.code == 8
        """, "test_rebound.py")
        kept = generate(rebound.read_text(), "test_rebound.py").source
        self.assertEqual(kept.count("with pytest.raises(expected) as info:"), 2)
        self.assertNotIn("_pyn_caught_", kept)
        result = runner.run_module(rebound, self.root, self.work / "rebound", "python", [], sys.executable, 60)
        reference = runner.oracle([rebound], self.root, self.work / "oracle-rebound", sys.executable, 60)
        self.assertEqual(result.state, "passed", result.error + result.stderr)
        self.assertEqual(runner.compare([result], reference), [])
        for body in ("return 1", "info = None", "print(info)"):
            with self.subTest(body=body):
                kept = generate("import pytest\nclass E(Exception):\n    pass\ndef helper():\n"
                                "    with pytest.raises(E) as info:\n        raise E()\n"
                                f"    assert info.value.args\n    {body}\n" if body != "return 1" else
                                "import pytest\nclass E(Exception):\n    pass\ndef helper():\n"
                                "    with pytest.raises(E) as info:\n        return 1\n"
                                "    assert info.value.args\n", "test_suite.py").source
                self.assertIn("with pytest.raises(E) as info:", kept)

    def test_scope_failures_are_cached_and_attributed(self):
        actual, _ = self.check("scope_failures")
        outcomes = self.outcomes(actual)
        self.assertEqual(outcomes["test_broken_one", "setup"], "error")
        self.assertEqual(outcomes["test_broken_two", "setup"], "error")
        self.assertEqual(outcomes["test_skipping_two", "setup"], "skipped")
        self.assertEqual(outcomes["test_setup_ran_once", "call"], "passed")
        # A scope ends in its last case's teardown, even one that is skipped.
        self.assertEqual(outcomes["TestLate::test_uses", "teardown"], "passed")
        self.assertEqual(outcomes["TestLate::test_last_in_class", "teardown"], "error")
        self.assertEqual(outcomes["test_skipped_last", "teardown"], "error")

    def suite_with_conftest(self):
        self.source(CONFTEST, "conftest.py")
        return [self.source(CONFTEST_FIRST, "test_first.py"), self.source(CONFTEST_SECOND, "test_second.py")]

    def check_conftest(self, mode):
        paths = self.suite_with_conftest()
        results = runner.run_suite(paths, self.root, self.work / mode, mode, shlex.split(NATIVE), sys.executable, 180)
        expected = runner.oracle(paths, self.root, self.work / "oracle", sys.executable, 60)
        self.assertEqual(runner.compare(results, expected), [], json.dumps(
            runner.outcome_differences(results, expected), indent=2))
        self.assertEqual([result.state for result in results], ["passed", "test-failed"],
                         results[0].error + results[0].stderr)
        self.assertEqual(len(expected["cases"]), 7)
        # The session ends in the last case of the last module.
        self.assertEqual(results[1].events[-1], {
            "nodeid": "test_second.py::test_last_ends_the_session", "phase": "teardown", "outcome": "error",
            "detail": "RuntimeError: session teardown\n"})

    def test_conftest_fixtures_span_modules(self):
        self.check_conftest("python")

    def test_node_ids_select_classes_and_end_scopes_as_run(self):
        selections = {
            ("TestA::test_two[2]", "test_plain", "TestA::test_one", "TestB::test_log"):
                ["grouped+", "two2", "grouped-", "whole+", "plain", "grouped+", "one", "grouped-"],
            # TestA contains its test_two: pytest keeps the class and its position.
            ("TestA::test_two", "TestB", "TestA"): ["grouped+", "three"],
            ("TestB::test_log", "TestA::test_two[1]", "TestA::test_two"): [],
        }
        for selectors, log in selections.items():
            with self.subTest(selectors=selectors):
                path = self.source(SELECTION.replace("EXPECTED", repr(log)))
                evidence = self.root / "evidence.json"
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as error:
                    status = runner.main([*(f"{path}::{selector}" for selector in selectors), "--root",
                                          str(self.root), "--mode", "python", "--work-dir", str(self.work),
                                          "--json", str(evidence)])
                report = json.loads(evidence.read_text())
                self.assertEqual(status, 0, error.getvalue())
                self.assertEqual(report["qualification"], "pytest-matched")
                self.assertEqual(report["results"][0]["cases"], report["oracle"]["cases"])

    def test_instance_state_is_shared_with_method_fixtures(self):
        # (CPython only: the compiler needs attributes that __init__ declares.)
        path = self.source("""
            import pytest
            class TestInstance:
                @pytest.fixture(autouse=True)
                def prepare(self):
                    self.value = 41
                    yield
                    assert self.value == 42
                def test_same_instance(self):
                    assert self.value == 41
                    self.value += 1
                def test_new_instance(self):
                    assert self.value == 41
                    self.value = 42
        """)
        actual = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 60)
        expected = runner.oracle([path], self.root, self.work / "oracle", sys.executable, 60)
        self.assertEqual(actual.state, "passed", actual.error + actual.stderr)
        self.assertEqual(runner.compare([actual], expected), [])

    def check_combined(self, mode):
        """Every suite as one program: one build covers them, as one pytest session does."""
        self.source("def increment(value: int) -> int:\n    return value + 1\n", "test_helpers.py")
        self.source(CONFTEST, "conftest.py")
        states = {"test_helpers.py": "empty", "test_first.py": "passed", "test_second.py": "passed"}
        self.source(CONFTEST_FIRST, "test_first.py")
        self.source(CONFTEST_SECOND, "test_second.py")
        for name, (source, state) in SUITES.items():
            self.source(source, f"test_{name}.py")
            states[f"test_{name}.py"] = state
        paths = sorted(self.root / name for name in states)
        results = runner.run_suite(paths, self.root, self.work / mode, mode, shlex.split(NATIVE), sys.executable, 300)
        expected = runner.oracle(paths, self.root, self.work / "oracle", sys.executable, 120)
        self.assertEqual(runner.compare(results, expected), [], results[0].error + results[0].stderr + json.dumps(
            runner.outcome_differences(results, expected), indent=2))
        self.assertEqual({result.path: result.state for result in results}, states)
        self.assertEqual(len(expected["cases"]), 126)
        # conftest.py's session fixture fails as the last case of the last module ends.
        self.assertEqual(results[-1].events[-1]["detail"], "RuntimeError: session teardown\n")
        return results

    def test_all_suites_share_one_session(self):
        self.check_combined("python")

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_jit_suites_under_gc_stress(self):
        # A scope's cached value must survive the tests between its first and last use.
        with patch.dict(os.environ, {"PYSTACHY_GC_STRESS_PROGRAM": "1", "PYSTACHY_IRCHECK": "1"}):
            results = self.check_combined("jit")
        self.assertTrue(results[0].assertion_operands, results[0].operand_build_error)

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_aot_conftest(self):
        # (examples/pytest_native/test_forms.py builds the other forms ahead of time.)
        self.check_conftest("aot")

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_relative_compiler_and_source_lines(self):
        path = self.source("""
            import pytest
            class Problem(Exception):
                def __init__(self, code: int) -> None:
                    super().__init__("problem")
                    self.code = code
            def test_reused():
                with pytest.raises(Problem) as info:
                    raise Problem(1)
                with pytest.raises(Problem) as info:
                    raise Problem(2)
                assert info.value.code == 2
        """)
        actual = runner.run_module(path, self.root, self.work, "jit", shlex.split(NATIVE), sys.executable, 180)
        # The compiler rejects the test, which is left out: nothing of it ran or passed.
        self.assertEqual((actual.state, actual.cases), ("empty", []))
        # The diagnostic names the test's line beside the generated one.
        self.assertRegex(actual.uncompiled["test_suite.py::test_reused"],
                         r"test_suite\.py:12 \[generated test_suite\.py:\d+\]: error: ")
        command = shlex.split(NATIVE)
        if len(command) == 1 and os.path.isabs(command[0]):
            relative = os.path.relpath(command[0])
            simple = self.source("def test_one():\n    assert 1 + 1 == 2\n", "test_simple.py")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as error:
                # --root differs from the directory the relative compiler path is given in.
                status = runner.main([str(simple), "--root", str(self.root), "--mode", "jit", "--compiler",
                                      relative if os.sep in relative else os.path.join(".", relative),
                                      "--work-dir", str(self.work / "relative")])
            self.assertEqual(status, 0, error.getvalue())


class FormRejections(TemporarySuite):
    def test_unsupported_forms_are_collection_errors(self):
        fixture = "import pytest\n"
        cases = {
            "class with an imported base": ("from helper import Base\nclass TestX(Base):\n    def test_a(self): pass\n",
                                            "imported or computed base classes"),
            "class with two bases": ("class A: pass\nclass B: pass\nclass TestX(A, B):\n    def test_a(self): pass\n",
                                     "several base classes"),
            "helper class with an imported base": ("from helper import Base\nclass Suite(Base):\n"
                                                   "    def test_a(self): pass\n", "cannot read"),
            "class keyword": ("class TestX(metaclass=type):\n    def test_a(self): pass\n", "class keywords"),
            "__init__": ("class TestX:\n    def __init__(self): pass\n    def test_a(self): pass\n", "__init__"),
            "nested class": ("class TestX:\n    class TestY:\n        def test_a(self): pass\n", "nested"),
            "conditional class": ("if True:\n    class TestX:\n        def test_a(self): pass\n", "nested and conditional"),
            "conditional method": ("class TestX:\n    if True:\n        def test_a(self): pass\n", "conditional"),
            "static test": ("class TestX:\n    @staticmethod\n    def test_a(): pass\n", "unsupported test decorator"),
            "method without self": ("class TestX:\n    def test_a(): pass\n", "require self"),
            "duplicate method": ("class TestX:\n    def test_a(self): pass\n    def test_a(self): pass\n", "duplicate"),
            "xunit class hook": ("class TestX:\n    def setup_class(cls): pass\n    def test_a(self): pass\n", "xunit"),
            "xunit method argument": ("class TestX:\n    def setup_method(self, method):\n        print(method)\n"
                                      "    def test_a(self): pass\n", "method argument of setup_method"),
            "xunit method call": ("class TestX:\n    def setup_method(self): pass\n"
                                  "    def test_a(self):\n        self.setup_method()\n", "through super"),
            "pytestmark twice": (fixture + "pytestmark = pytest.mark.slow\npytestmark = pytest.mark.fast\n",
                                 "assigned once"),
            "pytestmark read": (fixture + "pytestmark = pytest.mark.slow\nMARKS = pytestmark\n", "pytestmark"),
            "pytestmark filterwarnings": (fixture + "pytestmark = pytest.mark.filterwarnings('explode')\n",
                                          "built-in warning class"),
            "unittest runTest": ("import unittest\nclass Legacy(unittest.TestCase):\n    def runTest(self): pass\n",
                                 "unsupported unittest.TestCase method: runTest"),
            "class attribute table": (fixture + "CASES = [1]\nclass TestX:\n    CASES = [2]\n"
                                      "    @pytest.mark.parametrize('n', CASES)\n    def test_a(self, n): pass\n",
                                      "cannot use its attributes: CASES"),
            "class skipif call": (fixture + "def flag(): return True\nclass TestX:\n"
                                  "    @pytest.mark.skipif(flag(), reason='r')\n    def test_a(self): pass\n",
                                  "names, attributes, literals and comparisons"),
            "class skipif attribute": (fixture + "class TestX:\n    FLAG = True\n"
                                       "    @pytest.mark.skipif(FLAG == True, reason='r')\n    def test_a(self): pass\n",
                                       "cannot use its attributes: FLAG"),
            "self fixture call": (fixture + "class TestX:\n    @pytest.fixture\n    def value(self): return 1\n"
                                  "    def test_a(self):\n        assert self.value() == 1\n", "argument name"),
            "class fixture scope": (fixture + "class TestX:\n    @pytest.fixture(scope='class')\n"
                                    "    def value(self): return 1\n    def test_a(self, value): pass\n",
                                    "must be function-scoped"),
            "class fixture override": (fixture + "@pytest.fixture\ndef value(): return 1\nclass TestX:\n"
                                       "    @pytest.fixture\n    def value(self): return 2\n"
                                       "    def test_a(self, value): pass\n", "overriding a fixture"),
            "package scope": (fixture + "@pytest.fixture(scope='package')\ndef value(): return 1\n", "fixture scope"),
            "scoped params": (fixture + "@pytest.fixture(scope='module', params=[1])\ndef value(request):\n"
                              "    return request.param\n", "must be function-scoped"),
            "ids without params": (fixture + "@pytest.fixture(ids=['a'])\ndef value(): return 1\n", "require params"),
            "computed params": (fixture + "def cases(): return [1]\n@pytest.fixture(params=cases())\n"
                                "def value(request):\n    return request.param\n", "a table the collector can read"),
            "request without params": (fixture + "@pytest.fixture\ndef value(request): return request.node.name\n",
                                       "request.param"),
            "request node": (fixture + "@pytest.fixture(params=[1])\ndef value(request):\n"
                             "    return request.node\ndef test_a(value): pass\n", "request.param"),
            "request in a test": ("def test_a(request): pass\n", "unsupported fixture: request"),
            "scope mismatch": (fixture + "@pytest.fixture\ndef small(): return 1\n@pytest.fixture(scope='module')\n"
                               "def big(small): return small\ndef test_a(big): pass\n",
                               "big of module scope cannot request small of function scope"),
            "scope mismatch builtin": (fixture + "@pytest.fixture(scope='session')\ndef big(tmp_path): return 1\n"
                                       "def test_a(big): pass\n", "cannot request tmp_path"),
            "scope mismatch parameter": (fixture + "@pytest.fixture(scope='module')\ndef big(n): return n\n"
                                         "@pytest.mark.parametrize('n', [1])\ndef test_a(big, n): pass\n",
                                         "cannot request n of function scope"),
            "monkeypatch.delattr": ("import os\ndef test_a(monkeypatch):\n    monkeypatch.delattr(os, 'sep')\n",
                                    "monkeypatch.delattr is unsupported"),
            "pytester": ("def test_a(pytester): pass\n", "unsupported fixture: pytester"),
            "approx keyword": (fixture + "def test_a():\n    assert 1 == pytest.approx(1, extra=2)\n", "approx supports"),
            "empty raises tuple": (fixture + "def test_a():\n    with pytest.raises(()):\n        pass\n", "raises supports"),
            "raises check": (fixture + "def test_a():\n    with pytest.raises(ValueError, check=len):\n        pass\n",
                             "raises supports"),
            "xfail raises call": (fixture + "def kinds(): return ValueError\n@pytest.mark.xfail(raises=kinds())\n"
                                  "def test_a(): pass\n", "raises= requires"),
            "imported test function": ("from helper import test_other\n", "imported tests"),
            "dynamic test name": ("def make(): return []\ntest_cases = make()\n", "dynamically assigning"),
        }
        for name, (source, message) in cases.items():
            with self.subTest(form=name), self.assertRaisesRegex(CollectionError, message):
                generate(source, "test_suite.py")

    def test_conftest_rejections(self):
        cases = {
            "test": ("def test_a(): pass\n", "cannot define tests"),
            "class": ("class TestX:\n    def test_a(self): pass\n", "cannot define tests"),
            "hook": ("def pytest_configure(config): pass\n", "pytest_configure is not run natively"),
            "collection hook": ("def pytest_generate_tests(metafunc): pass\n", "unsupported pytest hook"),
            "plugins": ("pytest_plugins = ['x']\n", "pytest_plugins"),
            "parameter marks": ("import pytest\n@pytest.fixture(params=[pytest.param(1, marks=pytest.mark.skip)])\n"
                                "def value(request):\n    return request.param\n", "conftest.py fixture parameters"),
        }
        for name, (source, message) in cases.items():
            with self.subTest(form=name), self.assertRaisesRegex(CollectionError, message):
                generate_conftest(source, "conftest.py")
        _, shared = generate_conftest("import pytest\n@pytest.fixture\ndef value(): return 1\n", "conftest.py")
        # A module's fixture replaces the conftest.py one of its name, unless it asks for it.
        generate("import pytest\n@pytest.fixture\ndef value(): return 2\n", "test_suite.py", shared=shared)
        with self.assertRaisesRegex(CollectionError, "requests the fixture it overrides is unsupported: value"):
            generate("import pytest\n@pytest.fixture\ndef value(value): return 2\n", "test_suite.py", shared=shared)

    def test_conftest_files_apply_from_the_root_down(self):
        nested = self.source("def test_a(): pass\n", "tests/test_a.py")
        deeper = self.source("def test_b(): pass\n", "tests/unit/test_b.py")
        outer = self.source("", "conftest.py")
        inner = self.source("", "tests/unit/conftest.py")
        self.source("", "tests/data/conftest.py")
        paths = runner.discover([self.root], self.root)
        self.assertEqual(paths, [nested, deeper])
        tree = runner.layout(paths, self.root)
        # (tests/data has no selected test: its conftest.py applies to none.)
        self.assertEqual(tree.conftests, [outer, inner])
        self.assertEqual(tree.above(nested), [outer])
        self.assertEqual(tree.above(deeper), [outer, inner])
        self.assertEqual(tree.above(inner), [outer])
        self.assertEqual([tree.modules[path] for path in (nested, deeper)], ["test_a", "test_b"])
        self.assertEqual(len({tree.modules[outer], tree.modules[inner]}), 2)

    def test_conftest_is_not_a_test_module(self):
        path = self.source("def test_a(): pass\n", "conftest.py")
        with self.assertRaisesRegex(CollectionError, "expected a Python test module"):
            runner.discover([path], self.root)

    def test_conftest_collection_error_stops_the_suite(self):
        self.source("def pytest_collection_modifyitems(items): pass\n", "conftest.py")
        path = self.source("def test_a(): pass\n")
        actual = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 30)
        self.assertEqual(actual.state, "collection-error")
        # (run_module compares nothing with pytest, which such a hook needs.)
        self.assertIn("pytest_collection_modifyitems is not run natively", actual.error)


class RunnerDetails(TemporarySuite):
    def test_generated_lines_map_to_test_lines(self):
        source = textwrap.dedent('''\
            import pytest

            @pytest.fixture(scope="module")
            def value():
                return 1

            @pytest.mark.parametrize("n", [1, 2])
            def test_a(value, n):
                total = value + n
                with pytest.raises(ValueError):
                    int("x")
                assert total > 1
        ''')
        module = generate(source, "test_suite.py")
        lines = module.source.splitlines()

        def generated(text):
            return next(index for index, line in enumerate(lines, 1) if line.strip().startswith(text))

        self.assertEqual(original_line(module, generated("total = value + n")), 9)
        self.assertEqual(original_line(module, generated("int('x')")), 11)
        self.assertEqual(original_line(module, generated("assert ")), 12)
        # Generated code for a declaration reports at that declaration.
        self.assertEqual(original_line(module, generated("_pyn_param_0 = 1")), 8)
        self.assertEqual(original_line(module, generated("def _pyn_scope_get_value")), 4)
        self.assertEqual(original_line(module, generated("test_a(value=")), 8)
        self.assertIsNone(original_line(module, 1))
        self.assertIsNone(original_line(GeneratedModule("", []), 5))

    def test_scope_caches_take_the_fixture_annotation(self):
        source = generate(textwrap.dedent('''\
            import typing
            import pytest
            @pytest.fixture(scope="module")
            def names() -> typing.Iterator[list[str]]:
                yield []
            @pytest.fixture(scope="session")
            def table() -> "dict[str, int]":
                return {}
            @pytest.fixture(scope="class")
            def channel() -> typing.Generator[int, None, None]:
                yield 1
            @pytest.fixture(scope="module")
            def inferred():
                return [1]
            @pytest.fixture(scope="module")
            def effect() -> typing.Iterator[None]:
                yield
            def test_a(names, table, channel, inferred, effect): pass
        '''), "test_suite.py").source
        self.assertIn("_pyn_scope_value_names: 'list[list[str]]' = []", source)
        self.assertIn("_pyn_scope_value_table: 'list[dict[str, int]]' = []", source)
        self.assertIn("_pyn_scope_value_channel: 'list[int]' = []", source)
        self.assertIn("_pyn_scope_value_inferred = []", source)
        # A fixture that provides nothing has no cached value.
        self.assertNotIn("_pyn_scope_value_effect", source)

    def test_translate_names_source_lines(self):
        module = GeneratedModule("", [], lines={4: 10, 9: 12})
        sources = {"/work/test_a.py": ("tests/test_a.py", module)}
        self.assertEqual(runner.translate("/work/test_a.py:10: error: x (call at /work/test_a.py:5)\nother:3", sources),
                         "tests/test_a.py:12 [generated test_a.py:10]: error: x "
                         "(call at tests/test_a.py:10 [generated test_a.py:5])\nother:3")
        self.assertEqual(runner.translate("/work/test_a.py:2: error", sources), "/work/test_a.py:2: error")
        self.assertEqual(runner.translate("anything", {}), "anything")


if __name__ == "__main__":
    unittest.main()
