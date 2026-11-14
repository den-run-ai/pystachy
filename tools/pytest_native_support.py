"""Typed helpers for generated native tests; this is not the pytest package.

The build-time collector replaces supported pytest imports with this module.
Keep values in their native layouts: neither reporting nor exception handling
requires dynamic Any. Public compatibility is deliberately limited to the
forms accepted by the collector.
"""

import re
from types import TracebackType


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


class Raises:
    """The supported single-exception-class, string-regex raises context."""

    def __init__(self, expected: type[BaseException], match: str | None) -> None:
        if not isinstance(expected, type):
            unsupported("raises requires one exception class; exception tuples and non-class values are unsupported")
        if not issubclass(expected, BaseException):
            raise ValueError("Expected a BaseException type, but got " + repr(expected.__name__))
        # pytest validates the regex before entering the body. Deferring this
        # until __exit__ could run application side effects for an invalid test.
        if match is not None:
            try:
                re.compile(match)
            except re.error as error:
                fail("Invalid regex pattern provided to 'match': " + str(error))
        self.expected = expected
        self.match = match
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
            fail("DID NOT RAISE " + self.expected.__name__)
        if not issubclass(kind, self.expected):
            return False
        self._value = value
        self._type = kind
        pattern = self.match
        if pattern is not None:
            message = str(value)
            if re.search(pattern, message) is None:
                raise AssertionError("Regex pattern did not match.\n Regex: " + repr(pattern)
                                     + "\n Input: " + repr(message))
        return True

    @property
    def type(self) -> type[BaseException]:
        kind = self._type
        if kind is None:
            raise AssertionError(".type can only be used after the context manager exits")
        return kind


def raises(expected: type[BaseException], *, match: str | None = None) -> Raises:
    return Raises(expected, match)


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
