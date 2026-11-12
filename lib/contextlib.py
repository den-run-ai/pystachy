"""Utilities for with-statement contexts.  See PEP 343."""
# Pystachy port of CPython 3.13's Lib/contextlib.py (lib/provenance.md): contextmanager (also
# as a decorator, @cm() on a function), closing, nullcontext, suppress, ExitStack and
# AbstractContextManager, with CPython's code where the subset takes it. Each change is marked
# "Pystachy port". The async managers (asynccontextmanager, aclosing, AsyncExitStack,
# AbstractAsyncContextManager), redirect_stdout, redirect_stderr and chdir are not here:
# the subset has no async def, no assignable sys.stdout and no os.getcwd()
# (lib/compatibility.md).
import abc
from types import TracebackType
from typing import Callable, Self

__all__ = ["contextmanager", "closing", "nullcontext",
           "AbstractContextManager", "ContextDecorator",
           "suppress", "ExitStack"]


class AbstractContextManager(abc.ABC):

    """An abstract base class for context managers."""

    # Pystachy port: no __class_getitem__, __slots__ or __subclasshook__ (no class objects as
    # values, slots or virtual subclasses)

    def __enter__(self) -> Self:
        """Return `self` upon entering the runtime context."""
        return self

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        """Raise any exception triggered within the runtime context."""
        return None


class ContextDecorator(object):
    "A base class or mixin that enables context managers to work as decorators."

    def _recreate_cm(self):
        """Return a recreated instance of self.

        Allows an otherwise one-shot context manager like
        _GeneratorContextManager to support use as
        a decorator via implicit recreation.

        This is a private interface just for _GeneratorContextManager.
        See issue #11647 for details.
        """
        return self

    def __call__(self, func):
        # Pystachy port: no @wraps(func)
        def inner(*args, **kwds):
            with self._recreate_cm():
                return func(*args, **kwds)
        return inner


class _GeneratorContextManager:
    """Helper for @contextmanager decorator."""

    # Pystachy port: a class template, which derives from no class: _GeneratorContextManagerBase's
    # __init__ and _recreate_cm, and ContextDecorator's __call__ (without @wraps), are here (no
    # __doc__ of func's), and its caller makes the generator, func(*args, **kwds)
    def __init__(self, func, args, kwds, gen):
        self.gen = gen
        # Pystachy port: one field at a time (self.func, self.args, self.kwds = func, args, kwds)
        self.func = func
        self.args = args
        self.kwds = kwds
        # Pystachy port: whether __enter__ has deleted func, args and kwds (a field is not
        # deleted: reading one then raises CPython's AttributeError instead)
        self._deleted = False

    def _recreate_cm(self):
        # _GCMB instances are one-shot context managers, so the
        # CM must be recreated each time a decorated function is
        # called
        if self._deleted:
            raise AttributeError("'_GeneratorContextManager' object has no attribute 'func'")
        return _GeneratorContextManager(self.func, self.args, self.kwds, self.func(*self.args, **self.kwds))

    def __call__(self, func):
        def inner(*args, **kwds):
            with self._recreate_cm():
                return func(*args, **kwds)
        return inner

    def __enter__(self):
        # do not keep args and kwds alive unnecessarily
        # they are only needed for recreation, which is not possible anymore
        # Pystachy port: del self.args, self.kwds, self.func is the flag _deleted (a field is not
        # deleted); the del raises AttributeError for args when they are gone, a second __enter__
        if self._deleted:
            raise AttributeError("'_GeneratorContextManager' object has no attribute 'args'")
        self._deleted = True
        try:
            return next(self.gen)
        except StopIteration:
            raise RuntimeError("generator didn't yield") from None

    def __exit__(self, typ: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None) -> bool:
        if typ is None:
            try:
                next(self.gen)
            except StopIteration:
                return False
            else:
                try:
                    raise RuntimeError("generator didn't stop")
                finally:
                    self.gen.close()
        elif value is not None:
            # Pystachy port: (value is None: CPython makes the exception, typ(), to tell it
            # apart as it comes back) a with statement passes the exception, which is all
            # that this __exit__ takes
            try:
                self.gen.throw(value)
            except StopIteration as exc:
                # Suppress StopIteration *unless* it's the same exception that
                # was passed to throw().  This prevents a StopIteration
                # raised inside the "with" statement from being suppressed.
                return exc is not value
            except RuntimeError as exc:
                # Don't re-raise the passed in exception. (issue27122)
                if exc is value:
                    # Pystachy port: no exc.__traceback__ = traceback (no tracebacks)
                    return False
                # Avoid suppressing if a StopIteration exception
                # was passed to throw() and later wrapped into a RuntimeError
                # (see PEP 479 for sync generators; async generators also
                # have this behavior). But do this only if the exception wrapped
                # by the RuntimeError is actually Stop(Async)Iteration (see
                # issue29692).
                if (
                    isinstance(value, StopIteration)
                    and exc.__cause__ is value
                ):
                    # Pystachy port: no value.__traceback__ = traceback (no tracebacks)
                    return False
                raise
            except BaseException as exc:
                # only re-raise if it's *not* the exception that was
                # passed to throw(), because __exit__() must not raise
                # an exception unless __exit__() itself failed.  But throw()
                # has to raise the exception to signal propagation, so this
                # fixes the impedance mismatch between the throw() protocol
                # and the __exit__() protocol.
                if exc is not value:
                    raise
                return False
            try:
                raise RuntimeError("generator didn't stop after throw()")
            finally:
                self.gen.close()
        return False


class _GeneratorContextManagerFactory:
    # Pystachy port: what contextmanager() returns, CPython's helper(*args, **kwds), as an
    # object that a call makes a _GeneratorContextManager of (no @wraps(func))
    def __init__(self, func):
        self.func = func

    def __call__(self, /, *args, **kwds):
        return _GeneratorContextManager(self.func, args, kwds, self.func(*args, **kwds))


def contextmanager(func):
    """@contextmanager decorator.

    Typical usage:

        @contextmanager
        def some_generator(<arguments>):
            <setup>
            try:
                yield <value>
            finally:
                <cleanup>

    This makes this:

        with some_generator(<arguments>) as <variable>:
            <body>

    equivalent to this:

        <setup>
        try:
            <variable> = <value>
            <body>
        finally:
            <cleanup>
    """
    return _GeneratorContextManagerFactory(func)


class closing:
    """Context to automatically close something at the end of a block.

    Code like this:

        with closing(<module>.open(<arguments>)) as f:
            <block>

    is equivalent to this:

        f = <module>.open(<arguments>)
        try:
            <block>
        finally:
            f.close()

    """
    # Pystachy port: a class template, which derives from no class (AbstractContextManager)
    def __init__(self, thing):
        self.thing = thing
    def __enter__(self):
        return self.thing
    def __exit__(self, *exc_info):
        self.thing.close()


class suppress:
    """Context manager to suppress specified exceptions

    After the exception is suppressed, execution proceeds with the next
    statement following the with statement.

         with suppress(FileNotFoundError):
             os.remove(somefile)
         # Execution still resumes here if the file was already removed
    """

    # Pystachy port: a with statement whose item is a call of suppress() with exception classes
    # compiles to a try statement whose except clause catches them (the classes are no values of
    # the subset); the class is CPython's otherwise, but for exception groups (none in the subset),
    # and derives from no class (AbstractContextManager), as a class template

    def __init__(self, *exceptions):
        self._exceptions = exceptions

    def __enter__(self):
        pass

    def __exit__(self, exctype, excinst, exctb):
        # Unlike isinstance and issubclass, CPython exception handling
        # currently only looks at the concrete type hierarchy (ignoring
        # the instance and subclass checking hooks). While Guido considers
        # that a bug rather than a feature, it's a fairly hard one to fix
        # due to various internal implementation details. suppress provides
        # the simpler issubclass based semantics, rather than trying to
        # exactly reproduce the limitations of the CPython interpreter.
        #
        # See http://bugs.python.org/issue12029 for more details
        if exctype is None:
            return
        if issubclass(exctype, self._exceptions):
            return True
        return False


def _not_callable(exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> bool:
    # Pystachy port: the exit callback of ExitStack.push(None)
    raise TypeError("'NoneType' object is not callable")


# Inspired by discussions on http://bugs.python.org/issue13585
class ExitStack(AbstractContextManager):
    """Context manager for dynamic management of a stack of exit callbacks.

    For example:
        with ExitStack() as stack:
            files = [stack.enter_context(open(fname)) for fname in filenames]
            # All opened files will automatically be closed at the end of
            # the with statement, even if attempts to open files later
            # in the list raise an exception.
    """

    # Pystachy port: _BaseExitStack's methods are here (a class has one base, and there is no
    # AsyncExitStack to share them with). An exit callback is a closure of __exit__'s
    # signature that returns whether it suppresses the exception: enter_context(), push() and
    # callback() each make one, where CPython binds the manager's __exit__ with MethodType or
    # wraps the callback (_create_exit_wrapper, _create_cb_wrapper). The callbacks are a list
    # (CPython: a deque of (is_sync, callback) pairs, whose is_sync is always true here).

    def __init__(self) -> None:
        self._exit_callbacks: list[Callable[[type[BaseException] | None, BaseException | None, TracebackType | None], bool]] = []

    def pop_all(self) -> "ExitStack":
        """Preserve the context stack by transferring it to a new instance."""
        # Pystachy port: ExitStack() (CPython: type(self)(); no class derives from this one)
        new_stack = ExitStack()
        new_stack._exit_callbacks = self._exit_callbacks
        self._exit_callbacks = []
        return new_stack

    def push(self, exit):
        """Registers a callback with the standard __exit__ method signature.

        Can suppress exceptions the same way __exit__ method can.
        Also accepts any object with an __exit__ method (registering a call
        to the method instead of the object itself).
        """
        # Pystachy port: callable() and hasattr() test exit's static type, so that only the
        # call it has is compiled: a function, or an object whose class defines __call__(), is
        # the callback; any other object is a manager where its class defines __exit__()
        # (CPython tries type(exit).__exit__ first, also for an object that can be called, and
        # assumes that any other object is a callable; hasattr() of a function is not
        # supported). An object without either, which None is, fails as CPython's call of it
        # does, when the stack unwinds.
        if callable(exit):
            # Not a context manager, so assume it's a callable.
            self._push_exit_callback(exit)
        elif hasattr(exit, "__exit__"):
            self._push_cm_exit(exit)
        else:
            self._exit_callbacks.append(_not_callable)
        return exit  # Allow use as a decorator.

    def enter_context(self, cm):
        """Enters the supplied context manager.

        If successful, also pushes its __exit__ method as a callback and
        returns the result of the __enter__ method.
        """
        # Pystachy port: cm.__enter__() (CPython looks the two methods up on type(cm) and
        # raises TypeError where one is missing, which is a compile-time error here)
        result = cm.__enter__()
        self._push_cm_exit(cm)
        return result

    def callback(self, callback, /, *args, **kwds):
        """Registers an arbitrary callback and arguments.

        Cannot suppress exceptions.
        """
        def _exit_wrapper(exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> bool:
            callback(*args, **kwds)
            return False

        # Pystachy port: no _exit_wrapper.__wrapped__ = callback (a function has no attributes)
        self._exit_callbacks.append(_exit_wrapper)
        return callback  # Allow use as a decorator

    def _push_cm_exit(self, cm) -> None:
        """Helper to correctly register callbacks to __exit__ methods."""
        def _exit_wrapper(exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> bool:
            if cm.__exit__(exc_type, exc, tb):
                return True
            return False
        self._exit_callbacks.append(_exit_wrapper)

    def _push_exit_callback(self, callback) -> None:
        def _exit_wrapper(exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> bool:
            if callback(exc_type, exc, tb):
                return True
            return False
        self._exit_callbacks.append(_exit_wrapper)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> bool:
        received_exc = exc is not None

        # Pystachy port: no _fix_exception_context() (an exception's __context__ is not
        # read or written, and no traceback shows it)

        # Callbacks are invoked in LIFO order to match the behaviour of
        # nested context managers
        suppressed_exc = False
        pending_raise = False
        while self._exit_callbacks:
            cb = self._exit_callbacks.pop()
            try:
                # Pystachy port: no traceback (CPython passes exc.__traceback__)
                if exc is None:
                    suppress = cb(None, None, None)
                else:
                    suppress = cb(type(exc), exc, None)
                if suppress:
                    suppressed_exc = True
                    pending_raise = False
                    exc = None
            except BaseException as new_exc:
                pending_raise = True
                exc = new_exc

        if pending_raise:
            assert exc is not None
            raise exc
        return received_exc and suppressed_exc

    def close(self) -> None:
        """Immediately unwind the context stack."""
        self.__exit__(None, None, None)


class _NullContext(AbstractContextManager):
    # Pystachy port: nullcontext() without its enter_result, which is None (a field cannot hold
    # None alone)
    def __enter__(self) -> None:
        return None

    def __exit__(self, *excinfo):
        pass


class _NullContextResult:
    # Pystachy port: nullcontext(enter_result), a class template (which derives from no class)
    def __init__(self, enter_result):
        self.enter_result = enter_result

    def __enter__(self):
        return self.enter_result

    def __exit__(self, *excinfo):
        pass


def nullcontext(*enter_result):
    """Context manager that does no additional processing.

    Used as a stand-in for a normal context manager, when a particular
    block of code is only sometimes used with a normal context manager:

    cm = optional_cm if condition else nullcontext()
    with cm:
        # Perform operation, using optional_cm if condition is True
    """
    # Pystachy port: a function, which makes an object of one of two classes (no async
    # __aenter__ and __aexit__), decided by whether it is given enter_result (positional, and
    # not None alone: nullcontext(None) is nullcontext())
    if len(enter_result) == 0:
        return _NullContext()
    return _NullContextResult(enter_result[0])
