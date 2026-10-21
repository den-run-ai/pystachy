# Adapted from CPython 3.13.16 Lib/test/test_contextlib.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91: ContextManagerTestCase's
# test_contextmanager_plain, test_contextmanager_finally, test_contextmanager_no_reraise,
# test_contextmanager_trap_yield_after_throw, test_contextmanager_trap_no_yield,
# test_contextmanager_trap_second_yield, test_contextmanager_except,
# test_contextmanager_except_stopiter, test_contextmanager_except_pep479,
# test_contextmanager_do_not_unchain_non_stopiteration_exceptions,
# test_contextmanager_wrap_runtimeerror and test_keywords; ClosingTestCase's
# test_closing and test_closing_error; NullcontextTestCase.test_nullcontext;
# FileContextTestCase.testWithOpen; LockContextTestCase's testWithLock and testWithRLock;
# TestContextDecorator's test_contextdecorator, test_contextdecorator_with_exception,
# test_decorator, test_decorator_with_exception, test_decorating_method and
# test_contextmanager_as_decorator; TestSuppress's test_no_exception, test_exact_exception,
# test_exception_hierarchy, test_other_exception, test_no_args and test_multiple_exception_args.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual, assertIs, assertTrue and
# assertRaises print what they check. Generator functions and classes are annotated; a class's
# None-valued attributes are typed fields. __exit__(TypeError, TypeError("foo"), None) calls pass
# type(e) of the exception (classes are no values of the subset), and subTest loops are plain
# loops. mycontext keeps the class of the exception its __exit__ was given (or None) and how
# many arguments it took, where upstream keeps the tuple (its items have different types for
# each call); test_contextmanager_except reads str(e) where upstream reads e.args[0];
# test_decorating_method decorates a function that takes the object (an object is no decorator
# of a method here); and len(5), rejected as the program compiles, is a raise of its TypeError. The
# StopIteration subclass of test_contextmanager_except_stopiter is raised in a loop of its own
# (a list holds objects of one class). test_contextmanager_except_pep479 compiles the manager
# directly (no exec(); from __future__ import generator_stop is the default). threading's Lock
# and RLock are _thread's allocate_lock() and RLock() (no threading module); testWithOpen writes
# a file in a tempfile.mkdtemp() directory (no tempfile.mktemp()).
# EXCLUDED upstream cases:
# - TestAbstractContextManager, test_contextmanager_attribs, the docstring tests and
#   test_instance_docs: no class objects, __subclasshook__, setattr() of functions or __doc__
# - test_contextmanager_traceback, test_nokeepref, test_param_errors, test_contextmanager_trap_*'s
#   gi_suspended: tracebacks, weak references, frames and calls without arguments are rejected
# - test_recursive: a function that a manager decorates calls itself, through the decorator's
#   inner(), whose return type is inferred: rejected ("cannot infer what ... inner() returns: it
#   calls itself before a return statement does")
# - test_contextmanager_non_normalised: __exit__(RuntimeError, None, None) with no exception
#   (CPython's __exit__ makes one, typ()): a class is no value
# - testWithCondition, testWithSemaphore, testWithBoundedSemaphore: no threading module
# - test_typo_enter, test_typo_exit, test_contextdecorator_as_mixin: a class without __enter__ or
#   __exit__ in a with statement is rejected as the program compiles
# - TestBaseExitStack, TestExitStack, TestRedirectStream, TestRedirectStdout, TestRedirectStderr,
#   TestChdir, the async tests: not in lib/contextlib.py
# - TestSuppress's test_no_result_from_enter (with suppress(...) as x is rejected),
#   test_cm_is_reentrant (a suppress object outside a with statement's item is rejected),
#   test_exception_groups (no exception groups)
import _thread
import os
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager, nullcontext, suppress


def test_contextmanager_plain() -> None:
    state: list[int] = []
    @contextmanager
    def woohoo() -> Iterator[int]:
        state.append(1)
        yield 42
        state.append(999)
    with woohoo() as x:
        print("assertEqual", state, [1])
        print("assertEqual", x, 42)
        state.append(x)
    print("assertEqual", state, [1, 42, 999])


def test_contextmanager_finally() -> None:
    state: list[int] = []
    @contextmanager
    def woohoo() -> Iterator[int]:
        state.append(1)
        try:
            yield 42
        finally:
            state.append(999)
    try:
        with woohoo() as x:
            print("assertEqual", state, [1])
            print("assertEqual", x, 42)
            state.append(x)
            raise ZeroDivisionError()
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")
    print("assertEqual", state, [1, 42, 999])


def test_contextmanager_no_reraise() -> None:
    @contextmanager
    def whee() -> Iterator[None]:
        yield
    ctx = whee()
    ctx.__enter__()
    # Calling __exit__ should not result in an exception
    e = TypeError("foo")
    print("assertFalse", ctx.__exit__(type(e), e, None))


def test_contextmanager_trap_yield_after_throw() -> None:
    @contextmanager
    def whoo() -> Iterator[None]:
        try:
            yield
        except:
            yield
    ctx = whoo()
    ctx.__enter__()
    e = TypeError("foo")
    try:
        ctx.__exit__(type(e), e, None)
    except RuntimeError as r:
        print("assertRaises RuntimeError", r)


def test_contextmanager_trap_no_yield() -> None:
    @contextmanager
    def whoo() -> Iterator[None]:
        if False:
            yield
    ctx = whoo()
    try:
        ctx.__enter__()
    except RuntimeError as r:
        print("assertRaises RuntimeError", r)


def test_contextmanager_trap_second_yield() -> None:
    @contextmanager
    def whoo() -> Iterator[None]:
        yield
        yield
    ctx = whoo()
    ctx.__enter__()
    try:
        ctx.__exit__(None, None, None)
    except RuntimeError as r:
        print("assertRaises RuntimeError", r)


def test_contextmanager_except() -> None:
    state: list[int] = []
    @contextmanager
    def woohoo() -> Iterator[int]:
        state.append(1)
        try:
            yield 42
        except ZeroDivisionError as e:
            state.append(int(str(e)))
            print("assertEqual", state, [1, 42, 999])
    with woohoo() as x:
        print("assertEqual", state, [1])
        print("assertEqual", x, 42)
        state.append(x)
        raise ZeroDivisionError(999)
    print("assertEqual", state, [1, 42, 999])


class StopIterationSubclass(StopIteration):
    pass


def test_contextmanager_except_stopiter() -> None:
    @contextmanager
    def woohoo() -> Iterator[None]:
        yield

    for stop_exc in [StopIteration('spam')]:
        try:
            with woohoo():
                raise stop_exc
        except Exception as ex:
            print("assertIs", ex is stop_exc, type(ex).__name__)
        else:
            print(f'{stop_exc} was suppressed')
    for sub_exc in [StopIterationSubclass('spam')]:
        try:
            with woohoo():
                raise sub_exc
        except Exception as ex:
            print("assertIs", ex is sub_exc, type(ex).__name__)
        else:
            print(f'{sub_exc} was suppressed')


def test_contextmanager_except_pep479() -> None:
    @contextmanager
    def woohoo() -> Iterator[None]:
        yield

    stop_exc = StopIteration('spam')
    try:
        with woohoo():
            raise stop_exc
    except Exception as ex:
        print("assertIs", ex is stop_exc)
    else:
        print('StopIteration was suppressed')


def test_contextmanager_do_not_unchain_non_stopiteration_exceptions() -> None:
    @contextmanager
    def test_issue29692() -> Iterator[None]:
        try:
            yield
        except Exception as exc:
            raise RuntimeError('issue29692:Chained') from exc
    try:
        with test_issue29692():
            raise ZeroDivisionError
    except Exception as ex:
        print("assertIs", type(ex).__name__, "RuntimeError")
        print("assertEqual", str(ex), 'issue29692:Chained')
        print("assertIsInstance", isinstance(ex.__cause__, ZeroDivisionError))

    try:
        with test_issue29692():
            raise StopIteration('issue29692:Unchained')
    except Exception as ex:
        print("assertIs", type(ex).__name__, "StopIteration")
        print("assertEqual", str(ex), 'issue29692:Unchained')
        print("assertIsNone", ex.__cause__)


def test_contextmanager_wrap_runtimeerror() -> None:
    @contextmanager
    def woohoo() -> Iterator[None]:
        try:
            yield
        except Exception as exc:
            raise RuntimeError(f'caught {exc}') from exc

    try:
        with woohoo():
            1 / 0
    except RuntimeError as e:
        print("assertRaises RuntimeError", e)

    # If the context manager wrapped StopIteration in a RuntimeError,
    # we also unwrap it, because we can't tell whether the wrapping was
    # done by the generator machinery or by the generator itself.
    try:
        with woohoo():
            raise StopIteration
    except StopIteration as e:
        print("assertRaises StopIteration", repr(e))


def test_keywords() -> None:
    # Ensure no keyword arguments are inhibited
    @contextmanager
    def woohoo(self: int, func: int, args: int, kwds: int) -> Iterator[tuple[int, int, int, int]]:
        yield (self, func, args, kwds)
    with woohoo(self=11, func=22, args=33, kwds=44) as target:
        print("assertEqual", target, (11, 22, 33, 44))


class C:
    def __init__(self, state: list[int]) -> None:
        self.state = state

    def close(self) -> None:
        self.state.append(1)


def test_closing() -> None:
    state: list[int] = []
    x = C(state)
    print("assertEqual", state, "[]")
    with closing(x) as y:
        print("assertEqual", x is y)
    print("assertEqual", state, [1])


def test_closing_error() -> None:
    state: list[int] = []
    x = C(state)
    print("assertEqual", state, "[]")
    try:
        with closing(x) as y:
            print("assertEqual", x is y)
            1 / 0
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")
    print("assertEqual", state, [1])


class Plain:
    pass


def test_nullcontext() -> None:
    c = Plain()
    with nullcontext(c) as c_in:
        print("assertIs", c_in is c)


def testWithOpen() -> None:
    d = tempfile.mkdtemp()
    tfn = os.path.join(d, "booh.txt")
    try:
        with open(tfn, "w", encoding="utf-8") as f:
            print("assertFalse", f.closed)
            f.write("Booh\n")
        print("assertTrue", f.closed)
        try:
            with open(tfn, "r", encoding="utf-8") as f:
                print("assertFalse", f.closed)
                print("assertEqual", repr(f.read()), repr("Booh\n"))
                1 / 0
        except ZeroDivisionError:
            print("assertRaises ZeroDivisionError")
        print("assertTrue", f.closed)
    finally:
        os.remove(tfn)
        os.rmdir(d)


def testWithLock() -> None:
    lock = _thread.allocate_lock()
    print("assertFalse", lock.locked())
    with lock:
        print("assertTrue", lock.locked())
    print("assertFalse", lock.locked())
    try:
        with lock:
            print("assertTrue", lock.locked())
            1 / 0
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")
    print("assertFalse", lock.locked())


def testWithRLock() -> None:
    lock = _thread.RLock()
    print("assertFalse", lock._is_owned())
    with lock:
        print("assertTrue", lock._is_owned())
    print("assertFalse", lock._is_owned())
    try:
        with lock:
            print("assertTrue", lock._is_owned())
            1 / 0
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")
    print("assertFalse", lock._is_owned())


class mycontext:
    """Example decoration-compatible context manager for testing"""
    # (ContextDecorator's __call__, as a method of its own)
    def __init__(self) -> None:
        self.started = False
        self.exc = "unset"
        self.nexc = 0
        self.catch = False

    def __enter__(self) -> "mycontext":
        self.started = True
        return self

    def __exit__(self, *exc) -> bool:
        self.exc = type(exc[1]).__name__ if exc[1] is not None else "None"
        self.nexc = len(exc)
        return self.catch

    def __call__(self, func):
        def inner(*args, **kwds):
            with self:
                return func(*args, **kwds)
        return inner


def test_contextdecorator() -> None:
    context = mycontext()
    with context as result:
        print("assertIs", result is context)
        print("assertTrue", context.started)

    print("assertEqual", context.exc, context.nexc)


def test_contextdecorator_with_exception() -> None:
    context = mycontext()

    try:
        with context:
            raise NameError('foo')
    except NameError as e:
        print("assertRaisesRegex NameError", e)
    print("assertIs", context.exc)

    context = mycontext()
    context.catch = True
    with context:
        raise NameError('foo')
    print("assertIs", context.exc)


def test_decorator() -> None:
    context = mycontext()

    @context
    def test() -> None:
        print("assertIsNone", context.exc)
        print("assertTrue", context.started)
    test()
    print("assertEqual", context.exc, context.nexc)


def test_decorator_with_exception() -> None:
    context = mycontext()

    @context
    def test() -> None:
        print("assertIsNone", context.exc)
        print("assertTrue", context.started)
        raise NameError('foo')

    try:
        test()
    except NameError as e:
        print("assertRaisesRegex NameError", e)
    print("assertIs", context.exc)


method_context = mycontext()


class Test(object):
    def __init__(self) -> None:
        self.a = 0
        self.b = 0
        self.c: int | None = 0


@method_context
def method(self: Test, a: int, b: int, c: int | None = None) -> None:
    self.a = a
    self.b = b
    self.c = c


def test_decorating_method() -> None:
    # these tests are for argument passing when used as a decorator
    test = Test()
    method(test, 1, 2)
    print("assertEqual", test.a, 1)
    print("assertEqual", test.b, 2)
    print("assertEqual", test.c, None)

    method(test, a=1, b=2, c=3)
    print("assertEqual", test.a, 1)
    print("assertEqual", test.b, 2)
    print("assertEqual", test.c, 3)

    method(test, b=1, a=2)
    print("assertEqual", test.a, 2)
    print("assertEqual", test.b, 1)
    print("assertEqual", test.c, None)

    method(test, 1, b=2)
    print("assertEqual", test.a, 1)
    print("assertEqual", test.b, 2)


state: list[str] = []


@contextmanager
def woohoo_deco(y: str) -> Iterator[None]:
    state.append(y)
    yield
    state.append("999")


@woohoo_deco("1")
def decorated(x: str) -> None:
    print("assertEqual", state, ["1"])
    state.append(x)


def test_contextmanager_as_decorator() -> None:
    decorated('something')
    print("assertEqual", state, ["1", 'something', "999"])

    # Issue #11647: Ensure the decorated function is 'reusable'
    state.clear()
    decorated('something else')
    print("assertEqual", state, ["1", 'something else', "999"])


def test_no_exception() -> None:
    with suppress(ValueError):
        print("assertEqual", pow(2, 5), 32)


def test_exact_exception() -> None:
    with suppress(TypeError):
        raise TypeError("object of type 'int' has no len()")
    print("suppressed")


def test_exception_hierarchy() -> None:
    with suppress(LookupError):
        'Hello'[50]
    print("suppressed")


def test_other_exception() -> None:
    try:
        with suppress(TypeError):
            1/0
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")


def test_no_args() -> None:
    try:
        with suppress():
            1/0
    except ZeroDivisionError:
        print("assertRaises ZeroDivisionError")


def test_multiple_exception_args() -> None:
    with suppress(ZeroDivisionError, TypeError):
        1/0
    with suppress(ZeroDivisionError, TypeError):
        raise TypeError("object of type 'int' has no len()")
    print("suppressed")


test_contextmanager_plain()
test_contextmanager_finally()
test_contextmanager_no_reraise()
test_contextmanager_trap_yield_after_throw()
test_contextmanager_trap_no_yield()
test_contextmanager_trap_second_yield()
test_contextmanager_except()
test_contextmanager_except_stopiter()
test_contextmanager_except_pep479()
test_contextmanager_do_not_unchain_non_stopiteration_exceptions()
test_contextmanager_wrap_runtimeerror()
test_keywords()
test_closing()
test_closing_error()
test_nullcontext()
testWithOpen()
testWithLock()
testWithRLock()
test_contextdecorator()
test_contextdecorator_with_exception()
test_decorator()
test_decorator_with_exception()
test_decorating_method()
test_contextmanager_as_decorator()
test_no_exception()
test_exact_exception()
test_exception_hierarchy()
test_other_exception()
test_no_args()
test_multiple_exception_args()
