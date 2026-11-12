"""Typed helpers for generated native tests; this is not the pytest package.

The build-time collector replaces supported pytest imports with this module.
Keep values in their native layouts: neither reporting nor exception handling
requires dynamic Any. Public compatibility is deliberately limited to the
forms accepted by the collector.
"""

import math
import re
from types import TracebackType
from typing import Callable


class Failed(BaseException):
    """An explicit test failure, outside ordinary application exceptions."""


class Skipped(BaseException):
    """A test or fixture requested a skip."""


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

    def __init__(self, expected: list[type[BaseException]], match: str | None) -> None:
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
            fail("DID NOT RAISE " + " or ".join([expected.__name__ for expected in self.expected]))
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

    def match(self, pattern: str) -> bool:
        """ExceptionInfo.match: search the raised exception's text, or fail the assertion."""
        _search(pattern, str(self.value))
        return True


def raises(expected: type[BaseException], *, match: str | None = None) -> Raises:
    return Raises([expected], match)


def raises_any(expected: list[type[BaseException]], *, match: str | None = None) -> Raises:
    """pytest.raises((A, B)): the collector passes a literal tuple's classes as a list."""
    return Raises(expected, match)


def match_exception(pattern: str, message: str) -> bool:
    """ExceptionInfo.match for a raises block the collector expanded (typed .value)."""
    _search(pattern, message)
    return True


def check_pattern(pattern: str) -> None:
    """Reject an invalid match= regex before an expanded raises block runs its body."""
    try:
        re.compile(pattern)
    except re.error as error:
        fail("Invalid regex pattern provided to 'match': " + str(error))


def _number(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        unsupported("pytest.approx supports int and float values only")
    return float(value)


class Approx:
    """pytest.approx for one number: pytest's default and explicit tolerances."""

    def __init__(self, expected: float, rel: float, has_rel: bool, tolerance: float, has_abs: bool,
                 nan_ok: bool) -> None:
        self.expected = expected
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
        return repr(self.expected) + " ± " + repr(self.tolerance())


def approx(expected, rel=None, abs=None, nan_ok: bool = False) -> Approx:
    return Approx(_number(expected), 0.0 if rel is None else _number(rel), rel is not None,
                  0.0 if abs is None else _number(abs), abs is not None, nan_ok)


def approx_equal(actual, expected: Approx) -> bool:
    """`actual == pytest.approx(...)`, which the collector calls with operands in order.

    A number's own == does not consult Approx.__eq__ in compiled code.
    """
    return expected == actual


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
        if phase not in ("setup", "call", "teardown"):
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
        if self.errors or self.xfail_count > 1 or (self.xfail_count and self.skips):
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
