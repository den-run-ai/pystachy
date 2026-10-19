"""Utilities for with-statement contexts.  See PEP 343."""
# Pystachy port of CPython 3.13's Lib/contextlib.py (lib/provenance.md): contextmanager (also
# as a decorator, @cm() on a function), closing, nullcontext, suppress and
# AbstractContextManager, with CPython's code where the subset takes it. Each change is marked
# "Pystachy port". The async managers (asynccontextmanager, aclosing, AsyncExitStack,
# AbstractAsyncContextManager), ExitStack, redirect_stdout, redirect_stderr and chdir are not here:
# the subset has no async def, no list of managers of different classes, no assignable
# sys.stdout and no os.getcwd() (lib/compatibility.md).
import abc
from types import TracebackType
from typing import Self

__all__ = ["contextmanager", "closing", "nullcontext",
           "AbstractContextManager", "ContextDecorator",
           "suppress"]


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
