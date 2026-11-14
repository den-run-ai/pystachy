# Adapted from CPython 3.13.16 Lib/test/test_contextlib.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. Source SHA-256:
# b7b3a0f70a4c760743c99662de3e575711de671ce519780b0883e9a9ec94196c.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# TestExitStack's methods (TestBaseExitStack's, with exit_stack = ExitStack) become functions
# of the same names; assertEqual, assertIs and assertRaises print or assert what they check.
# CPython's own contextlib records the oracle, while JIT/AOT execute lib/contextlib.py.
# Complete: test_no_resources, test_close, test_pop_all, test_exit_raise, test_exit_suppress,
# test_body_exception_suppress and test_exit_exception_non_suppressing, with these edits: a
# callback is registered by a call, stack.callback(_exit), where upstream decorates a nested
# function with @stack.callback; results are module lists; raise_exc() is given an exception,
# where upstream gives its class (a class is no value here); 1/0 is a division by a variable.
# Partial: test_callback (the calls and their order, with the callback's keywords named and its
# record a str; not __wrapped__, __name__ and __doc__ of the wrappers, and not the three calls
# without a callback, which do not compile),
# test_push (not the reads of stack._exit_callbacks, whose items are closures here),
# test_enter_context (likewise), test_exit_exception_chaining_suppress (the last callback
# raises KeyError by a lookup in a dict that has a type), test_excessive_nesting (a function
# that takes no argument, where upstream registers int) and test_dont_reraise_RuntimeError
# (the exception's class and message; not its __context__ and __cause__).
# Not claimed: test_instance_docs, test_enter_context_errors and test_instance_bypass (a class
# without __enter__ or __exit__ is a compile-time error), and the methods that read tracebacks
# or __context__: test_exit_exception_traceback, test_exit_exception_chaining_reference,
# test_exit_exception_chaining, test_exit_exception_explicit_none_context,
# test_exit_exception_with_correct_context and test_exit_exception_with_existing_context.
from contextlib import ExitStack, contextmanager
from types import TracebackType

ZERO = 0


# test_contextlib.TestExitStack.test_no_resources
def test_no_resources() -> None:
    with ExitStack():
        pass
    print('TestExitStack.test_no_resources')


callback_result: list[str] = []


def _exit_callback(*args, example: int = 0, self: int = 0, callback: int = 0) -> None:
    """Test metadata propagation"""
    callback_result.append('%r example=%d self=%d callback=%d' % (args, example, self, callback))


# test_contextlib.TestExitStack.test_callback
def test_callback() -> None:
    expected = [
        "() example=0 self=0 callback=0",
        "(1,) example=0 self=0 callback=0",
        "(1, 2) example=0 self=0 callback=0",
        "() example=1 self=0 callback=0",
        "(1,) example=1 self=0 callback=0",
        "(1, 2) example=1 self=0 callback=0",
        "(1, 2) example=0 self=3 callback=4",
    ]
    with ExitStack() as stack:
        stack.callback(_exit_callback, 1, 2, self=3, callback=4)
        stack.callback(_exit_callback, 1, 2, example=1)
        stack.callback(_exit_callback, 1, example=1)
        stack.callback(_exit_callback, example=1)
        stack.callback(_exit_callback, 1, 2)
        stack.callback(_exit_callback, 1)
        stack.callback(_exit_callback)
    assert callback_result == expected, callback_result
    print('TestExitStack.test_callback')


def _expect_exc(exc_type: type[BaseException] | None, exc: BaseException | None, exc_tb: TracebackType | None) -> None:
    assert isinstance(exc, ZeroDivisionError)
    print('_expect_exc', type(exc).__name__)


def _suppress_exc(*exc_details) -> bool:
    print('_suppress_exc')
    return True


def _expect_ok(exc_type: type[BaseException] | None, exc: BaseException | None, exc_tb: TracebackType | None) -> None:
    assert exc_type is None
    assert exc is None
    assert exc_tb is None
    print('_expect_ok')


class ExitCM(object):
    def __init__(self, check_exc) -> None:
        self.check_exc = check_exc

    def __enter__(self) -> None:
        raise AssertionError("Should not be called!")

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, exc_tb: TracebackType | None) -> None:
        self.check_exc(exc_type, exc, exc_tb)


# test_contextlib.TestExitStack.test_push
def test_push() -> None:
    with ExitStack() as stack:
        stack.push(_expect_ok)
        cm = ExitCM(_expect_ok)
        stack.push(cm)
        stack.push(_suppress_exc)
        cm2 = ExitCM(_expect_exc)
        stack.push(cm2)
        stack.push(_expect_exc)
        stack.push(_expect_exc)
        1 / ZERO
    print('TestExitStack.test_push')


enter_result: list[int] = []


class TestCM(object):
    def __enter__(self) -> None:
        enter_result.append(1)

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, exc_tb: TracebackType | None) -> None:
        enter_result.append(3)


def _exit_enter() -> None:
    enter_result.append(4)


# test_contextlib.TestExitStack.test_enter_context
def test_enter_context() -> None:
    cm = TestCM()
    with ExitStack() as stack:
        stack.callback(_exit_enter)  # Registered first => cleaned up last
        stack.enter_context(cm)
        enter_result.append(2)
    assert enter_result == [1, 2, 3, 4], enter_result
    print('TestExitStack.test_enter_context')


close_result: list[int] = []


def _exit_close() -> None:
    close_result.append(1)


# test_contextlib.TestExitStack.test_close
def test_close() -> None:
    with ExitStack() as stack:
        stack.callback(_exit_close)
        stack.close()
        close_result.append(2)
    assert close_result == [1, 2], close_result
    print('TestExitStack.test_close')


pop_result: list[int] = []


def _exit_pop() -> None:
    pop_result.append(3)


# test_contextlib.TestExitStack.test_pop_all
def test_pop_all() -> None:
    with ExitStack() as stack:
        stack.callback(_exit_pop)
        new_stack = stack.pop_all()
        pop_result.append(1)
    pop_result.append(2)
    new_stack.close()
    assert pop_result == [1, 2, 3], pop_result
    print('TestExitStack.test_pop_all')


# test_contextlib.TestExitStack.test_exit_raise
def test_exit_raise() -> None:
    try:
        with ExitStack() as stack:
            stack.push(lambda *exc: False)
            1 / ZERO
        raise AssertionError("ZeroDivisionError not raised")
    except ZeroDivisionError as e:
        print('ZeroDivisionError', e)
    print('TestExitStack.test_exit_raise')


# test_contextlib.TestExitStack.test_exit_suppress
def test_exit_suppress() -> None:
    with ExitStack() as stack:
        stack.push(lambda *exc: True)
        1 / ZERO
    print('TestExitStack.test_exit_suppress')


def raise_exc(exc: Exception) -> None:
    raise exc


def suppress_exc(*exc_details) -> bool:
    return True


# test_contextlib.TestExitStack.test_exit_exception_non_suppressing
def test_exit_exception_non_suppressing() -> None:
    # http://bugs.python.org/issue19092
    try:
        with ExitStack() as stack:
            stack.callback(lambda: None)
            stack.callback(raise_exc, IndexError())
        raise AssertionError("Expected IndexError, but no exception was raised")
    except Exception as exc:
        assert isinstance(exc, IndexError)

    try:
        with ExitStack() as stack:
            stack.callback(raise_exc, KeyError())
            stack.push(suppress_exc)
            stack.callback(raise_exc, IndexError())
        raise AssertionError("Expected KeyError, but no exception was raised")
    except Exception as exc:
        assert isinstance(exc, KeyError)
    print('TestExitStack.test_exit_exception_non_suppressing')


# test_contextlib.TestExitStack.test_body_exception_suppress
def test_body_exception_suppress() -> None:
    try:
        with ExitStack() as stack:
            stack.push(suppress_exc)
            1 / ZERO
    except IndexError:
        raise AssertionError("Expected no exception, got IndexError")
    print('TestExitStack.test_body_exception_suppress')


EMPTY: dict[int, int] = {}


# test_contextlib.TestExitStack.test_exit_exception_chaining_suppress
def test_exit_exception_chaining_suppress() -> None:
    with ExitStack() as stack:
        stack.push(lambda *exc: True)
        stack.push(lambda *exc: 1 / ZERO)
        stack.push(lambda *exc: EMPTY[1])
    print('TestExitStack.test_exit_exception_chaining_suppress')


def nothing() -> int:
    return 0


# test_contextlib.TestExitStack.test_excessive_nesting
def test_excessive_nesting() -> None:
    # The original implementation would die with RecursionError here
    with ExitStack() as stack:
        for i in range(10000):
            stack.callback(nothing)
    print('TestExitStack.test_excessive_nesting')


class UniqueException(Exception):
    pass


class UniqueRuntimeError(RuntimeError):
    pass


@contextmanager
def second():
    try:
        yield 1
    except Exception as exc:
        raise UniqueException("new exception") from exc


@contextmanager
def first():
    try:
        yield 1
    except Exception as exc:
        raise exc


# test_contextlib.TestExitStack.test_dont_reraise_RuntimeError
def test_dont_reraise_RuntimeError() -> None:
    # https://bugs.python.org/issue27122
    # The UniqueRuntimeError should be caught by second()'s exception
    # handler which chain raised a new UniqueException.
    try:
        with ExitStack() as es_ctx:
            es_ctx.enter_context(second())
            es_ctx.enter_context(first())
            raise UniqueRuntimeError("please no infinite loop.")
        raise AssertionError("UniqueException not raised")
    except UniqueException as exc:
        print(type(exc).__name__, exc)
    print('TestExitStack.test_dont_reraise_RuntimeError')


test_no_resources()
test_callback()
test_push()
test_enter_context()
test_close()
test_pop_all()
test_exit_raise()
test_exit_suppress()
test_exit_exception_non_suppressing()
test_body_exception_suppress()
test_exit_exception_chaining_suppress()
test_excessive_nesting()
test_dont_reraise_RuntimeError()
