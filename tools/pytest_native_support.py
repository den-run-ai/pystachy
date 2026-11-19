"""Typed helpers for generated native tests; this is not the pytest package.

The build-time collector replaces supported pytest imports with this module.
Keep values in their native layouts: neither reporting nor exception handling
requires dynamic Any. Public compatibility is deliberately limited to the
forms accepted by the collector.
"""

import math
import re
from types import TracebackType
import warnings
from typing import Callable


class Failed(BaseException):
    """An explicit test failure, outside ordinary application exceptions."""


class Skipped(BaseException):
    """A test or fixture requested a skip."""


# unittest.SkipTest, which pytest reports as it does its own skip.
SkipTest = Skipped


class XFailed(BaseException):
    """A test or fixture requested an expected failure."""


class UnsupportedOperation(BaseException):
    """An unsupported helper form invalidates the whole execution."""


_unsupported_operation: str = ""


def unsupported(reason: str) -> None:
    # A test may catch BaseException or carry an xfail mark. Keep this outside
    # test outcomes so neither can turn an unsupported helper operation green.
    global _unsupported_operation
    _unsupported_operation = reason
    raise UnsupportedOperation(reason)


def condition(value) -> bool:
    """A skipif condition's truth, where the decorator evaluated an expression."""
    if isinstance(value, str):
        # pytest evaluates a string condition as code in the test module.
        unsupported("string skipif conditions are unsupported; use an expression")
    return bool(value)


def describe(error: BaseException) -> str:
    """pytest's short text of a failure: the exception's class name and str()."""
    if isinstance(error, Failed):
        return "Failed: " + str(error)
    text = str(error)
    if text:
        return type(error).__name__ + ": " + text
    return type(error).__name__


def fail(reason: str = "") -> None:
    raise Failed(reason)


def skip(reason: str = "") -> None:
    raise Skipped(reason)


def xfail(reason: str = "") -> None:
    raise XFailed(reason)


def saferepr(value) -> str:
    """repr() for an assertion message: a failing __repr__ must not replace the failure."""
    try:
        return repr(value)
    except KeyboardInterrupt:
        raise
    except BaseException as error:
        return "<[" + describe(error) + " raised in repr()] object>"


def _search(pattern: str, message: str) -> None:
    if re.search(pattern, message) is None:
        raise AssertionError("Regex pattern did not match.\n Regex: " + repr(pattern)
                             + "\n Input: " + repr(message))


class Raises:
    """The supported raises context: exception classes and an optional string regex."""

    def __init__(self, expected: list[type[BaseException]], match: str | None, unit: bool = False) -> None:
        for kind in expected:
            if not isinstance(kind, type):
                unsupported("raises requires an exception class or a literal tuple of classes")
            if not issubclass(kind, BaseException):
                raise ValueError("Expected a BaseException type, but got " + repr(kind.__name__))
        # pytest validates the regex before entering the body. Deferring this
        # until __exit__ could run application side effects for an invalid test.
        if match is not None:
            try:
                re.compile(match)
            except re.error as error:
                fail("Invalid regex pattern provided to 'match': " + str(error))
        self.expected = expected
        self._pattern = match
        self._unit = unit  # unittest's assertRaises: a missing exception is an AssertionError
        self._value: BaseException | None = None
        self._type: type[BaseException] | None = None

    @property
    def value(self) -> BaseException:
        value = self._value
        if value is None:
            raise AssertionError(".value can only be used after the context manager exits")
        return value

    def __enter__(self) -> "Raises":
        return self

    def __exit__(self, kind: type[BaseException] | None,
                 value: BaseException | None, traceback: TracebackType | None) -> bool:
        if kind is None:
            names = " or ".join([expected.__name__ for expected in self.expected])
            if self._unit:
                # unittest's failureException, which an enclosing assertRaises(AssertionError) catches.
                raise AssertionError(names + " not raised")
            fail("DID NOT RAISE " + names)
        matched = False
        for expected in self.expected:
            if issubclass(kind, expected):
                matched = True
        if not matched:
            return False
        self._value = value
        self._type = kind
        pattern = self._pattern
        if pattern is not None:
            _search(pattern, str(value))
        return True

    @property
    def type(self) -> type[BaseException]:
        kind = self._type
        if kind is None:
            raise AssertionError(".type can only be used after the context manager exits")
        return kind

    @property
    def typename(self) -> str:
        return self.type.__name__

    @property
    def exception(self) -> BaseException:
        """unittest's name for .value, on the context of assertRaises."""
        return self.value

    def match(self, pattern: str) -> bool:
        """ExceptionInfo.match: search the raised exception's text, or fail the assertion."""
        _search(pattern, str(self.value))
        return True


def raises(expected: type[BaseException], *, match: str | None = None) -> Raises:
    return Raises([expected], match)


def raises_any(expected: list[type[BaseException]], *, match: str | None = None) -> Raises:
    """pytest.raises((A, B)): the collector passes a literal tuple's classes as a list."""
    return Raises(expected, match)


def match_exception(pattern: str | None, message: str) -> bool:
    """ExceptionInfo.match for a raises block the collector expanded (typed .value).

    match=None is no pattern, as in pytest.raises.
    """
    if pattern is not None:
        _search(pattern, message)
    return True


def check_pattern(pattern: str | None) -> None:
    """Reject an invalid match= regex before an expanded raises block runs its body."""
    if pattern is None:
        return
    try:
        re.compile(pattern)
    except re.error as error:
        fail("Invalid regex pattern provided to 'match': " + str(error))


def recorded(caught: list[warnings.WarningMessage] | None) -> list[warnings.WarningMessage]:
    """The list that `warnings.catch_warnings(record=True)` appends to."""
    if caught is None:
        raise RuntimeError("warnings are not being recorded")
    return caught


def check_warnings(caught: list[warnings.WarningMessage], expected: list[type[BaseException]],
                   match: str | None) -> None:
    """After a `with pytest.warns(...)` block: one recorded warning must be of an expected
    class and, with match=, have that pattern in its text."""
    for item in caught:
        for kind in expected:
            if issubclass(item.category, kind) and (match is None or re.search(match, str(item.message)) is not None):
                return
    names = " or ".join([kind.__name__ for kind in expected])
    if match is None:
        fail("DID NOT WARN. No warnings of type " + names + " were emitted.")
    fail("DID NOT WARN. No warnings of type " + names + " matching the regex were emitted.\n Regex: " + match)


def _number(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        unsupported("pytest.approx supports int and float values only")
    return float(value)


def _whole(value) -> int:
    """An int's own value, which a float cannot hold beyond 2**53; 0 for another number."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _within(difference: int, tolerance: float) -> bool:
    """difference <= tolerance for a non-negative int, without rounding it to a float."""
    if tolerance >= 9223372036854775808.0:
        return True
    return difference <= int(tolerance)


class Approx:
    """pytest.approx for one number: pytest's default and explicit tolerances."""

    def __init__(self, expected: float, whole: int, is_whole: bool, rel: float, has_rel: bool, tolerance: float,
                 has_abs: bool, nan_ok: bool) -> None:
        self.expected = expected
        # An int expected value: compared with an int exactly, as pytest compares them.
        self.whole = whole
        self.is_whole = is_whole
        self.rel = rel
        self.has_rel = has_rel
        self.abs = tolerance
        self.has_abs = has_abs
        self.nan_ok = nan_ok

    def tolerance(self) -> float:
        # As pytest does, tolerances are checked when a comparison needs them: an exact
        # match never reads them.
        absolute = self.abs if self.has_abs else 1e-12
        if absolute < 0.0:
            raise ValueError("absolute tolerance can't be negative: " + repr(absolute))
        if math.isnan(absolute):
            raise ValueError("absolute tolerance can't be NaN.")
        if not self.has_rel and self.has_abs:
            return absolute
        relative = (self.rel if self.has_rel else 1e-6) * abs(self.expected)
        if relative < 0.0:
            raise ValueError("relative tolerance can't be negative: " + repr(relative))
        if math.isnan(relative):
            raise ValueError("relative tolerance can't be NaN.")
        return max(relative, absolute)

    def __eq__(self, actual: object) -> bool:
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            return False
        if isinstance(actual, int):
            if self.is_whole:
                # Floats would round two ints beyond 2**53 to one value: these subtract exactly.
                if actual == self.whole:
                    return True
                return _within(abs(self.whole - actual), self.tolerance())
        number = float(actual)
        if number == self.expected:
            return True
        if math.isnan(self.expected):
            return self.nan_ok and math.isnan(number)
        if math.isinf(self.expected):
            return False
        return abs(self.expected - number) <= self.tolerance()

    def __repr__(self) -> str:
        if math.isnan(self.expected) or math.isinf(self.expected):
            return repr(self.expected)
        return (repr(self.whole) if self.is_whole else repr(self.expected)) + " ± " + repr(self.tolerance())


def approx(expected, rel=None, abs=None, nan_ok: bool = False) -> Approx:
    return Approx(_number(expected), _whole(expected), isinstance(expected, int) and not isinstance(expected, bool),
                  0.0 if rel is None else _number(rel), rel is not None,
                  0.0 if abs is None else _number(abs), abs is not None, nan_ok)


def approx_equal(actual, expected: Approx) -> bool:
    """`actual == pytest.approx(...)`, which the collector calls with operands in order.

    A number's own == does not consult Approx.__eq__ in compiled code.
    """
    return expected == actual


def table_length(actual: int, expected: int, name: str) -> None:
    """Stop a run whose parameter table is not the one the collector read from the source."""
    if actual != expected:
        unsupported("parameter table " + name + " has " + str(actual) + " rows where its source shows "
                    + str(expected) + ": the module changes it while it is imported")


def parameter_value(actual: str, expected: str, source: str) -> None:
    """Stop a run whose parameter is not the value the collector read through an import for the test's ID."""
    if actual != expected:
        unsupported("parameter " + source + " is " + actual + " where the collector read " + expected
                    + " from the sources: the program computes another value, or a module changes what the "
                    "test module imports")


# The outcomes of the running unittest case's subtests, in order, and whether one is
# running: only then is a subTest block's failure reported apart and the test continued.
subtest_outcomes: list[str] = []
subtest_details: list[str] = []
unit_running = [False]
unit_expecting = [False]  # the running test method is decorated with unittest.expectedFailure
subtest_open: list[bool] = []  # each subTest block being run: whether none nested in it failed or skipped


class SubTest:
    """`with self.subTest():` a block whose failure is reported while its test goes on."""

    def __enter__(self) -> "SubTest":
        subtest_open.append(True)
        return self

    def __exit__(self, kind: type[BaseException] | None,
                 value: BaseException | None, traceback: TracebackType | None) -> bool:
        clean = subtest_open.pop() if subtest_open else True
        if value is None:
            # (unittest reports a success only where no subtest nested in this one failed or skipped.)
            if unit_running[0] and clean:
                subtest_outcomes.append("passed")
                subtest_details.append("")
            return False
        for index in range(len(subtest_open)):
            subtest_open[index] = False
        if isinstance(value, (KeyboardInterrupt, UnsupportedOperation)) or not unit_running[0]:
            # (Outside a case the runner drives, nothing would report what the block raised.)
            return False
        if isinstance(value, Skipped):
            subtest_outcomes.append("skipped")
            subtest_details.append(str(value))
        elif unit_expecting[0]:
            # unittest stops an expectedFailure test at its first failing subtest, which is
            # the failure it expects: the test method ends here with it (UnitRun.raised).
            return False
        else:
            subtest_outcomes.append("failed")
            subtest_details.append(describe(value))
        return True


class TestCase:
    """The part of unittest.TestCase that generated tests call; the runner drives its phases.

    A test class's setUp becomes its __init__ (the collector renames it), so the fields
    that setUp assigns are declared as any class's are. Assertions take values of any
    types and compare them as unittest does.
    """
    maxDiff: int | None
    longMessage: bool

    def __init__(self) -> None:
        pass

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def subTest(self) -> SubTest:
        return SubTest()

    def skipTest(self, reason: str = "") -> None:
        raise Skipped(reason)

    def fail(self, msg=None) -> None:
        raise AssertionError("None" if msg is None else str(msg))

    def _failure(self, standard: str, msg) -> None:
        raise AssertionError(standard if msg is None else standard + " : " + str(msg))

    def assertEqual(self, first, second, msg=None) -> None:
        if not first == second:
            self._failure(saferepr(first) + " != " + saferepr(second), msg)

    def assertNotEqual(self, first, second, msg=None) -> None:
        if not first != second:
            self._failure(saferepr(first) + " == " + saferepr(second), msg)

    def assertTrue(self, expr, msg=None) -> None:
        if not expr:
            self._failure(saferepr(expr) + " is not true", msg)

    def assertFalse(self, expr, msg=None) -> None:
        if expr:
            self._failure(saferepr(expr) + " is not false", msg)

    def assertIs(self, first, second, msg=None) -> None:
        if first is not second:
            self._failure(saferepr(first) + " is not " + saferepr(second), msg)

    def assertIsNot(self, first, second, msg=None) -> None:
        if first is second:
            self._failure("unexpectedly identical: " + saferepr(first), msg)

    def assertIsNone(self, obj, msg=None) -> None:
        if obj is not None:
            self._failure(saferepr(obj) + " is not None", msg)

    def assertIsNotNone(self, obj, msg=None) -> None:
        if obj is None:
            self._failure("unexpectedly None", msg)

    def assertIn(self, member, container, msg=None) -> None:
        if member not in container:
            self._failure(saferepr(member) + " not found in " + saferepr(container), msg)

    def assertNotIn(self, member, container, msg=None) -> None:
        if member in container:
            self._failure(saferepr(member) + " unexpectedly found in " + saferepr(container), msg)

    def assertGreater(self, a, b, msg=None) -> None:
        if not a > b:
            self._failure(saferepr(a) + " not greater than " + saferepr(b), msg)

    def assertGreaterEqual(self, a, b, msg=None) -> None:
        if not a >= b:
            self._failure(saferepr(a) + " not greater than or equal to " + saferepr(b), msg)

    def assertLess(self, a, b, msg=None) -> None:
        if not a < b:
            self._failure(saferepr(a) + " not less than " + saferepr(b), msg)

    def assertLessEqual(self, a, b, msg=None) -> None:
        if not a <= b:
            self._failure(saferepr(a) + " not less than or equal to " + saferepr(b), msg)

    def assertAlmostEqual(self, first, second, places: int | None = None, msg=None, delta=None) -> None:
        if first == second:
            return
        if delta is not None and places is not None:
            raise TypeError("specify delta or places not both")
        difference = abs(first - second)
        if delta is not None:
            if difference <= delta:
                return
            self._failure(saferepr(first) + " != " + saferepr(second) + " within " + saferepr(delta) + " delta", msg)
        elif round(difference, 7 if places is None else places) != 0:
            self._failure(saferepr(first) + " != " + saferepr(second) + " within "
                          + str(7 if places is None else places) + " places", msg)

    def assertNotAlmostEqual(self, first, second, places: int | None = None, msg=None, delta=None) -> None:
        if delta is not None and places is not None:
            raise TypeError("specify delta or places not both")
        difference = abs(first - second)
        if delta is not None:
            if not first == second and difference > delta:
                return
            self._failure(saferepr(first) + " == " + saferepr(second) + " within " + saferepr(delta) + " delta", msg)
        elif first == second or round(difference, 7 if places is None else places) == 0:
            self._failure(saferepr(first) + " == " + saferepr(second) + " within "
                          + str(7 if places is None else places) + " places", msg)

    def assertRegex(self, text: str, expected_regex: str, msg=None) -> None:
        if re.search(expected_regex, text) is None:
            self._failure("Regex didn't match: " + repr(expected_regex) + " not found in " + repr(text), msg)

    def assertNotRegex(self, text: str, unexpected_regex: str, msg=None) -> None:
        if re.search(unexpected_regex, text) is not None:
            self._failure("Regex matched: " + repr(unexpected_regex) + " matches in " + repr(text), msg)

    def assertSequenceEqual(self, seq1, seq2, msg=None) -> None:
        # (Items compare by position: a list may equal a tuple here.)
        equal = len(seq1) == len(seq2)
        if equal:
            for index in range(len(seq1)):
                if not seq1[index] == seq2[index]:
                    equal = False
                    break
        if not equal:
            self._failure("Sequences differ: " + saferepr(seq1) + " != " + saferepr(seq2), msg)

    def assertListEqual(self, list1, list2, msg=None) -> None:
        self.assertEqual(list1, list2, msg)

    def assertTupleEqual(self, tuple1, tuple2, msg=None) -> None:
        self.assertEqual(tuple1, tuple2, msg)

    def assertSetEqual(self, set1, set2, msg=None) -> None:
        self.assertEqual(set1, set2, msg)

    def assertDictEqual(self, d1, d2, msg=None) -> None:
        self.assertEqual(d1, d2, msg)

    def assertMultiLineEqual(self, first: str, second: str, msg=None) -> None:
        self.assertEqual(first, second, msg)

    def assertCountEqual(self, first, second, msg=None) -> None:
        # The same items the same number of times, in any order.
        remaining = list(second)
        equal = True
        for item in first:
            if item in remaining:
                remaining.remove(item)
            else:
                equal = False
        if not equal or remaining:
            self._failure("Element counts were not equal: " + saferepr(first) + " != " + saferepr(second), msg)

    def assertRaises(self, expected: type[BaseException]) -> Raises:
        return Raises([expected], None, True)

    def assertRaisesRegex(self, expected: type[BaseException], expected_regex: str) -> Raises:
        return Raises([expected], expected_regex, True)

    def assertRaisesAny(self, expected: list[type[BaseException]]) -> Raises:
        return Raises(expected, None, True)

    def assertRaisesRegexAny(self, expected: list[type[BaseException]], expected_regex: str) -> Raises:
        return Raises(expected, expected_regex, True)


def _quote(text: str) -> str:
    """Encode one JSON string without making report records dynamic values."""
    result = '"'
    digits = "0123456789abcdef"
    for character in text:
        code = ord(character)
        if character == '"':
            result += '\\"'
        elif character == "\\":
            result += "\\\\"
        elif character == "\n":
            result += "\\n"
        elif character == "\r":
            result += "\\r"
        elif character == "\t":
            result += "\\t"
        elif code < 32 or 55296 <= code <= 57343:
            result += ("\\u" + digits[(code >> 12) & 15]
                       + digits[(code >> 8) & 15] + digits[(code >> 4) & 15]
                       + digits[code & 15])
        else:
            result += character
    return result + '"'


class Report:
    """Write phase events to a dedicated file and certify normal completion.

    A missing completion record is an execution/protocol error, never a passing
    suite. The host validates node IDs, event order and expected case counts.
    Test stdout has no role in this protocol.
    """

    def __init__(self, path: str) -> None:
        self.stream = open(path, "w", encoding="utf-8")
        self.failed = False
        self.events = 0
        self.closed = False

    def record(self, nodeid: str, phase: str, outcome: str, detail: str = "") -> None:
        if self.closed:
            raise RuntimeError("native test report is closed")
        if phase not in ("setup", "subtest", "call", "teardown"):
            raise ValueError("invalid native test phase: " + phase)
        if outcome not in ("passed", "failed", "error", "skipped", "xfailed", "xpassed"):
            raise ValueError("invalid native test outcome: " + outcome)
        if outcome in ("failed", "error"):
            self.failed = True
        self.events += 1
        self.stream.write('{"nodeid":' + _quote(nodeid) + ',"phase":' + _quote(phase)
                          + ',"outcome":' + _quote(outcome) + ',"detail":' + _quote(detail)
                          + '}\n')
        self.stream.flush()

    def finish(self) -> int:
        if self.closed:
            raise RuntimeError("native test report is closed")
        if _unsupported_operation:
            self.stream.close()
            self.closed = True
            # No completion record: the hosted controller must classify this as
            # an execution error, even if every test caught or xfailed the error.
            raise UnsupportedOperation(_unsupported_operation)
        code = 0
        if self.failed:
            code = 1
        elif self.events == 0:
            code = 5
        self.stream.write('{"complete":true,"exit_code":' + str(code) + '}\n')
        self.stream.close()
        self.closed = True
        return code


# Finalizers of fixtures whose scope outlives one test, most recent last. A case ends
# its class, module or session scope by draining them (Teardown.scopes).
class_finalizers: list[Callable[[], None]] = []
module_finalizers: list[Callable[[], None]] = []
session_finalizers: list[Callable[[], None]] = []


class Teardown:
    """One case's teardown outcomes: its own fixtures, then the scopes ending with it."""

    def __init__(self) -> None:
        # 0: no xfail mark applies; 1: xfail; 2: xfail(raises=...), judged by matched.
        self.mode = 0
        self.errors = ""
        self.skips = ""
        self.xfails = ""
        self.error_count = 0
        self.xfail_count = 0
        self.matched = 0
        self.scope_errors: list[BaseException] = []
        # A unittest case's second failure, which pytest reports in place of the teardown's.
        self.override = ""
        self.override_detail = ""

    def skipped(self, reason: str) -> None:
        self.skips += reason + "\n"

    def xfailed(self, reason: str) -> None:
        self.xfails += reason + "\n"
        self.xfail_count += 1

    def failed(self, detail: str, matched: bool = False) -> None:
        self.errors += detail + "\n"
        self.error_count += 1
        if matched:
            self.matched += 1

    def _drain(self, pending: list[Callable[[], None]]) -> None:
        while pending:
            finalizer = pending.pop()
            try:
                finalizer()
            except Skipped as error:
                self.skipped(str(error))
            except XFailed as error:
                self.xfailed(str(error))
            except KeyboardInterrupt:
                raise
            except BaseException as error:
                self.failed(describe(error))
                self.scope_errors.append(error)

    def scopes(self, level: int) -> None:
        """Finish the class (1), module (2) and session (3) scopes that end here."""
        if level >= 1:
            self._drain(class_finalizers)
        if level >= 2:
            self._drain(module_finalizers)
        if level >= 3:
            self._drain(session_finalizers)

    def record(self, report: Report, nodeid: str) -> None:
        if self.override:
            report.record(nodeid, "teardown", "error" if self.override == "failed" else self.override,
                          self.override_detail)
        elif self.errors or self.xfail_count > 1 or (self.xfail_count and self.skips):
            # One failure, or pytest's group of several teardown exceptions.
            expected = self.mode == 1 or (self.mode == 2 and self.error_count == 1 and self.matched == 1
                                          and not self.skips and not self.xfails)
            report.record(nodeid, "teardown", "xfailed" if expected else "error",
                          self.errors + self.skips + self.xfails)
        elif self.skips:
            report.record(nodeid, "teardown", "skipped", self.skips)
        elif self.xfails:
            report.record(nodeid, "teardown", "xfailed", self.xfails)
        else:
            report.record(nodeid, "teardown", "passed", "")


class UnitRun:
    """What one unittest case's setUp, test and tearDown raised, as pytest reports it.

    pytest keeps each failure, error and skip that unittest reports. The first becomes
    the call's outcome and a second the teardown's; later ones are not reported.
    """

    def __init__(self) -> None:
        self.outcomes: list[str] = []
        self.details: list[str] = []
        self.expected = False
        self.expected_detail = ""
        unit_running[0] = True
        unit_expecting[0] = False
        subtest_open.clear()

    def expecting(self, now: bool) -> None:
        """Whether the test method of an expectedFailure case is running now."""
        unit_expecting[0] = now

    def skip(self, reason: str) -> None:
        self.outcomes.append("skipped")
        self.details.append(reason)

    def raised(self, error: BaseException, expecting: bool = False) -> None:
        if isinstance(error, Skipped):
            self.skip(str(error))
        elif isinstance(error, XFailed):
            self.outcomes.append("xfailed")
            self.details.append(str(error))
        elif expecting:
            # (unittest.expectedFailure: reported only if nothing else goes wrong.)
            self.expected = True
            self.expected_detail = describe(error)
        else:
            self.outcomes.append("failed")
            self.details.append(describe(error))

    def finish(self, report: Report, nodeid: str, expecting: bool, teardown: Teardown) -> None:
        failed_subtest = False
        for index in range(len(subtest_outcomes)):
            if subtest_outcomes[index] != "passed":
                failed_subtest = True
            report.record(nodeid, "subtest", subtest_outcomes[index], subtest_details[index])
        subtest_outcomes.clear()
        subtest_details.clear()
        unit_running[0] = False
        if expecting and not self.outcomes and not failed_subtest:
            if self.expected:
                self.outcomes.append("xfailed")
                self.details.append(self.expected_detail)
            else:
                self.outcomes.append("failed")
                self.details.append("Unexpected success")
        if self.outcomes:
            report.record(nodeid, "call", self.outcomes[0], self.details[0])
        else:
            report.record(nodeid, "call", "passed", "")
        if len(self.outcomes) > 1:
            teardown.override = self.outcomes[1]
            teardown.override_detail = self.details[1]
