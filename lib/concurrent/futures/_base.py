# Copyright 2009 Brian Quinlan. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

# Pystachy port of CPython 3.13.16's Lib/concurrent/futures/_base.py (lib/provenance.md), for the
# one thread a Pystachy program runs (docs/concurrency.md). An executor runs a call before
# submit() returns (thread.py), so its futures are finished; a future is pending only where a
# program makes a Future() itself, and nothing but that program's own code can finish it. So the
# module needs no lock, condition or waiter, and a wait that only another thread could end
# raises RuntimeError, as _thread's does, or sleeps for its timeout. Each change is marked
# "Pystachy port".

__author__ = 'Brian Quinlan (brian@sweetapp.com)'

import collections
# Pystachy port: no logging (LOGGER, below), no threading (the note above) and no types (Future
# is a Generic class); sys and traceback report a callback's exception, typing's names type
# Future, and builtins gives the module its TimeoutError (see below)
import sys
from builtins import TimeoutError
import time
import traceback
from typing import Callable, Generic, Self, TypeVar

# Pystachy port: the type of a future's result (see Future)
_T = TypeVar("_T")

FIRST_COMPLETED = 'FIRST_COMPLETED'
FIRST_EXCEPTION = 'FIRST_EXCEPTION'
ALL_COMPLETED = 'ALL_COMPLETED'
_AS_COMPLETED = '_AS_COMPLETED'

# Possible future states (for internal use by the futures package).
PENDING = 'PENDING'
RUNNING = 'RUNNING'
# The future was cancelled by the user...
CANCELLED = 'CANCELLED'
# ...and _Waiter.add_cancelled() was called by a worker.
CANCELLED_AND_NOTIFIED = 'CANCELLED_AND_NOTIFIED'
FINISHED = 'FINISHED'

_FUTURE_STATES = [
    PENDING,
    RUNNING,
    CANCELLED,
    CANCELLED_AND_NOTIFIED,
    FINISHED
]

_STATE_TO_DESCRIPTION_MAP = {
    PENDING: "pending",
    RUNNING: "running",
    CANCELLED: "cancelled",
    CANCELLED_AND_NOTIFIED: "cancelled",
    FINISHED: "finished"
}

# Pystachy port: no LOGGER = logging.getLogger("concurrent.futures"): logging is compiled with
# dynamic Any, which a program that only submits calls would pay for. What CPython logs there, an
# exception that a callback raises, is written to sys.stderr as logging's last resort handler
# writes it for a program that configures no logging: the message, then the exception
def _log_exception(msg: str, exc: BaseException) -> None:
    sys.stderr.write(msg + "\n" + "".join(traceback.format_exception(exc)))

# Pystachy port: the number that a future's repr and messages show, where CPython's show id(): an
# object's identity hash without its sign (the subset has id() of Any values only)
def _id(o) -> int:
    return hash(o) & 0xffffffffffff

# Pystachy port: the name of the class of a future's result, which its repr shows. The subset
# has type(x).__name__ of the builtin types and of objects of classes (#486), which the result's
# static type selects here; a function, a method or an object that is called has no class to
# name, and is shown as a function
def _class_name(value) -> str:
    if value is None:
        return "NoneType"
    elif isinstance(value, (bool, int, float, str, bytes, list, dict, tuple, set, frozenset)):
        return value.__class__.__name__
    elif callable(value):
        return "function"
    else:
        return value.__class__.__name__

class Error(Exception):
    """Base class for all future-related exceptions."""
    pass

class CancelledError(Error):
    """The Future was cancelled."""
    pass

# Pystachy port: no TimeoutError = TimeoutError, a local alias for the standard exception: a
# module-level assignment that reads the name it binds does not find the builtin, so the alias
# is imported above

class InvalidStateError(Error):
    """The operation is not allowed in this state."""
    pass

# Pystachy port: no _Waiter, _AsCompletedWaiter, _FirstCompletedWaiter, _AllCompletedWaiter,
# _AcquireFutures, _create_and_install_waiters() and _yield_finished_futures(): they let wait()
# and as_completed() sleep until another thread finishes a future, and here no other thread
# runs. While CPython would wait, no future changes, so a wait is _wait()'s. A waiter also
# records the futures that finish in the order they do, which as_completed() yields them in:
# here each future that finishes takes the next number of this count as its _order
_finished = 0

def _next_finished() -> int:
    global _finished
    _finished += 1
    return _finished

_DEADLOCK = " would wait for ever, as Pystachy runs no other thread to finish the future"

def _wait(what: str, timeout) -> None:
    # the wait for a future that is not done and that only this thread could finish: for ever
    # (RuntimeError, as _thread's acquire() of a lock that no thread would release), or for the
    # seconds of the timeout, as CPython's Condition.wait() and Event.wait() sleep them
    if timeout is None:
        raise RuntimeError("deadlock: " + what + _DEADLOCK)
    elif timeout > 0:
        time.sleep(timeout)


def as_completed(fs, timeout=None):
    """An iterator over the given futures that yields each as it completes.

    Args:
        fs: The sequence of Futures (possibly created by different
            Executors) to iterate over.
        timeout: The maximum number of seconds to wait.  If None, then
            there is no limit on the wait time.

    Returns:
        An iterator that yields the given Futures as they complete
        (finished or cancelled).  If any given Futures are duplicated,
        they will be returned once.

    Raises:
        TimeoutError: If the entire result iterator could not be generated
            before the given timeout.
    """
    if timeout is not None:
        end_time = timeout + time.monotonic()

    # Pystachy port: the futures are kept in the order given, each once, where CPython keeps
    # sets of them and a waiter that records those that finish: it yields the finished ones in
    # the order of a set, which is no particular one, and here it is the order given
    seen = set()
    futures = []
    for f in fs:
        if f not in seen:
            seen.add(f)
            futures.append(f)
    total_futures = len(futures)
    finished = [f for f in futures
                if f._state in [CANCELLED_AND_NOTIFIED, FINISHED]]
    pending = [f for f in futures
               if f._state not in [CANCELLED_AND_NOTIFIED, FINISHED]]
    for f in finished:
        yield f

    while pending:
        if timeout is None:
            wait_timeout = None
        else:
            wait_timeout = end_time - time.monotonic()
            if wait_timeout < 0:
                raise TimeoutError(
                        '%d (of %d) futures unfinished' % (
                        len(pending), total_futures))

        # Pystachy port: waiter.event.wait(wait_timeout) and the waiter's finished futures: the
        # pending futures that the program's own code has finished since the last yield, in
        # the order they finished in (see _next_finished()). Where there is none, none
        # finishes during the wait either
        finished = [f for f in pending
                    if f._state in [CANCELLED_AND_NOTIFIED, FINISHED]]
        finished.sort(key=lambda f: f._order)
        if not finished:
            if timeout is None:
                _wait("as_completed()", None)
            else:
                _wait("as_completed()", wait_timeout)
        pending = [f for f in pending
                   if f._state not in [CANCELLED_AND_NOTIFIED, FINISHED]]
        for f in finished:
            yield f

DoneAndNotDoneFutures = collections.namedtuple(
        'DoneAndNotDoneFutures', 'done not_done')
def wait(fs, timeout=None, return_when=ALL_COMPLETED):
    """Wait for the futures in the given sequence to complete.

    Args:
        fs: The sequence of Futures (possibly created by different
            Executors) to wait upon.
        timeout: The maximum number of seconds to wait.  If None, then
            there is no limit on the wait time.
        return_when: Indicates when this function should return.
            The options are:

            FIRST_COMPLETED - Return when any future finishes or is
                              cancelled.
            FIRST_EXCEPTION - Return when any future finishes by raising an
                              exception.  If no future raises an exception
                              then it is equivalent to ALL_COMPLETED.
            ALL_COMPLETED -   Return when all futures finish or are
                              cancelled.

    Returns:
        A named 2-tuple of sets. The first set, named 'done', contains the
        futures that completed (is finished or cancelled) before the wait
        completed. The second set, named 'not_done', contains uncompleted
        futures. Duplicate futures given to *fs* are removed and will be
        returned only once.
    """
    # Pystachy port: the set has a name of its own (a parameter keeps its type)
    fset = set(fs)
    done = {f for f in fset
               if f._state in [CANCELLED_AND_NOTIFIED, FINISHED]}
    not_done = fset - done
    if (return_when == FIRST_COMPLETED) and done:
        return DoneAndNotDoneFutures(done, not_done)
    elif (return_when == FIRST_EXCEPTION) and done:
        if any(f for f in done
               if not f.cancelled() and f.exception() is not None):
            return DoneAndNotDoneFutures(done, not_done)

    if len(done) == len(fset):
        return DoneAndNotDoneFutures(done, not_done)

    # Pystachy port: _create_and_install_waiters()'s check of return_when, then the wait, during
    # which no future finishes: the sets are those above
    if return_when != FIRST_COMPLETED and return_when != FIRST_EXCEPTION and return_when != ALL_COMPLETED:
        raise ValueError("Invalid return condition: %r" % return_when)
    _wait("wait()", timeout)
    return DoneAndNotDoneFutures(done, fset - done)


def _result_or_cancel(fut, timeout=None):
    # Pystachy port: no del fut, which breaks a reference cycle for CPython's reference counts
    try:
        return fut.result(timeout)
    finally:
        fut.cancel()


class Future(Generic[_T]):
    """Represents the result of an asynchronous computation."""

    # Pystachy port: a generic class of the result's type, where CPython's is a class of object
    # with __class_getitem__ = classmethod(types.GenericAlias): a field has one type, so
    # Future[int] holds an int's result and Future[None] that of a call that returns None, and a
    # program that makes a future itself names its type (Future[int](), f: Future[int] =
    # Future()). The result is held in a tuple of one item, None before there is one.
    # _call, which CPython's __init__ does not take, is an executor's (thread.py): a tuple of
    # that field's first value, whose type binds _T; the tuple of a call that returns None
    # binds nothing (no type variable is None), fits the annotation's first member and leaves
    # _T to the Future[None] that the executor names
    def __init__(self, _call: tuple[tuple[None] | None] | tuple[tuple[_T] | None] | None = None) -> None:
        """Initializes the future. Should not be called by clients."""
        # Pystachy port: no _condition and no _waiters (see the note on _Waiter above); the
        # fields are annotated
        self._state: str = PENDING
        self._result: tuple[_T] | None = None
        if _call is not None:
            self._result = _call[0]
        self._exception: BaseException | None = None
        self._order: int = 0  # Pystachy port: (see _next_finished())
        self._done_callbacks: list[Callable[[Self], None]] = []

    def _invoke_callbacks(self):
        for callback in self._done_callbacks:
            try:
                callback(self)
            except Exception as exc:
                _log_exception('exception calling callback for %r' % self, exc)

    def __repr__(self):
        # Pystachy port: _id(self) for id(self). The states and their descriptions are written
        # out, for FINISHED and _STATE_TO_DESCRIPTION_MAP[self._state]: this method is compiled
        # where an annotation first names a Future[...], and reads no global there
        state = ("pending" if self._state == 'PENDING' else
                 "running" if self._state == 'RUNNING' else
                 "finished" if self._state == 'FINISHED' else "cancelled")
        if self._state == 'FINISHED':
            if self._exception:
                return '<%s at %#x state=%s raised %s>' % (
                    self.__class__.__name__,
                    _id(self),
                    state,
                    self._exception.__class__.__name__)
            else:
                return '<%s at %#x state=%s returned %s>' % (
                    self.__class__.__name__,
                    _id(self),
                    state,
                    self._result_type())
        return '<%s at %#x state=%s>' % (
                self.__class__.__name__,
                _id(self),
               state)

    # Pystachy port: self._result.__class__.__name__, of the tuple's item (see __init__)
    def _result_type(self) -> str:
        r = self._result
        if r is not None:
            return _class_name(r[0])
        return "NoneType"

    def cancel(self):
        """Cancel the future if possible.

        Returns True if the future was cancelled, False otherwise. A future
        cannot be cancelled if it is running or has already completed.
        """
        if self._state in [RUNNING, FINISHED]:
            return False

        if self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]:
            return True

        self._state = CANCELLED

        self._invoke_callbacks()
        return True

    def cancelled(self):
        """Return True if the future was cancelled."""
        return self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]

    def running(self):
        """Return True if the future is currently executing."""
        return self._state == RUNNING

    def done(self):
        """Return True if the future was cancelled or finished executing."""
        return self._state in [CANCELLED, CANCELLED_AND_NOTIFIED, FINISHED]

    def __get_result(self):
        if self._exception is not None:
            # Pystachy port: no try/finally that sets self to None (it breaks a reference cycle
            # for CPython's reference counts)
            raise self._exception
        else:
            # Pystachy port: the tuple's item (see __init__); a finished future without an
            # exception holds one
            r = self._result
            if r is not None:
                return r[0]
            raise InvalidStateError('{}: {!r}'.format(self._state, self))

    def add_done_callback(self, fn):
        """Attaches a callable that will be called when the future finishes.

        Args:
            fn: A callable that will be called with this future as its only
                argument when the future completes or is cancelled.  The
                callable will always be called by a thread in the same
                process in which it was added.  If the future has already
                completed or been cancelled then the callable will be
                called immediately.  These callables are called in the
                order that they were added.
        """
        if self._state not in [CANCELLED, CANCELLED_AND_NOTIFIED, FINISHED]:
            # Pystachy port: a list holds callables of one type, so each callback is kept as a
            # function of this future that returns None, which calls it
            def call(future: Self) -> None:
                fn(future)
            self._done_callbacks.append(call)
            return
        try:
            fn(self)
        except Exception as exc:
            _log_exception('exception calling callback for %r' % self, exc)

    def result(self, timeout=None):
        """Return the result of the call that the future represents.

        Args:
            timeout: The number of seconds to wait for the result if the
                future isn't done.  If None, then there is no limit on the
                wait time.

        Returns:
            The result of the call that the future represents.

        Raises:
            CancelledError: If the future was cancelled.
            TimeoutError: If the future didn't finish executing before the
                given timeout.
            Exception: If the call raised then that exception will be
                raised.
        """
        if self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]:
            raise CancelledError()
        elif self._state == FINISHED:
            return self.__get_result()

        _wait("result()", timeout)

        if self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]:
            raise CancelledError()
        elif self._state == FINISHED:
            return self.__get_result()
        else:
            raise TimeoutError()

    def exception(self, timeout=None):
        """Return the exception raised by the call that the future represents.

        Args:
            timeout: The number of seconds to wait for the exception if the
                future isn't done.  If None, then there is no limit on the
                wait time.

        Returns:
            The exception raised by the call that the future represents or
            None if the call completed without raising.

        Raises:
            CancelledError: If the future was cancelled.
            TimeoutError: If the future didn't finish executing before the
                given timeout.
        """

        if self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]:
            raise CancelledError()
        elif self._state == FINISHED:
            return self._exception

        _wait("exception()", timeout)

        if self._state in [CANCELLED, CANCELLED_AND_NOTIFIED]:
            raise CancelledError()
        elif self._state == FINISHED:
            return self._exception
        else:
            raise TimeoutError()

    # The following methods should only be used by Executors and in tests.
    def set_running_or_notify_cancel(self):
        """Mark the future as running or process any cancel notifications.

        Should only be used by Executor implementations and unit tests.

        If the future has been cancelled (cancel() was called and returned
        True) then any threads waiting on the future completing (though
        calls to as_completed() or wait()) are notified and False is
        returned.

        If the future was not cancelled then it is put in the running state
        (future calls to running() will return True) and True is returned.

        This method should be called by Executor implementations before
        executing the work associated with this future. If this method
        returns False then the work should not be executed.

        Returns:
            False if the Future was cancelled, True otherwise.

        Raises:
            RuntimeError: if this method was already called or if
                set_result() or set_exception() was called.
        """
        if self._state == CANCELLED:
            self._state = CANCELLED_AND_NOTIFIED
            # Pystachy port: (waiter.add_cancelled(self), see _next_finished())
            self._order = _next_finished()
            return False
        elif self._state == PENDING:
            self._state = RUNNING
            return True
        else:
            # Pystachy port: (CPython also logs 'Future %s in unexpected state: %s' as critical)
            sys.stderr.write('Future %s in unexpected state: %s\n' % (_id(self), self._state))
            raise RuntimeError('Future in unexpected state')

    def set_result(self, result):
        """Sets the return value of work associated with the future.

        Should only be used by Executor implementations and unit tests.
        """
        if self._state in {CANCELLED, CANCELLED_AND_NOTIFIED, FINISHED}:
            raise InvalidStateError('{}: {!r}'.format(self._state, self))
        self._result = (result,)  # Pystachy port: (see __init__)
        self._state = FINISHED
        self._order = _next_finished()  # Pystachy port: (waiter.add_result(self))
        self._invoke_callbacks()

    def set_exception(self, exception):
        """Sets the result of the future as being the given exception.

        Should only be used by Executor implementations and unit tests.
        """
        if self._state in {CANCELLED, CANCELLED_AND_NOTIFIED, FINISHED}:
            raise InvalidStateError('{}: {!r}'.format(self._state, self))
        self._exception = exception
        self._state = FINISHED
        self._order = _next_finished()  # Pystachy port: (waiter.add_exception(self))
        self._invoke_callbacks()


class Executor(object):
    """This is an abstract base class for concrete asynchronous executors."""

    def submit(self, fn, /, *args, **kwargs):
        """Submits a callable to be executed with the given arguments.

        Schedules the callable to be executed as fn(*args, **kwargs) and
        returns a Future instance representing the execution of the
        callable.

        Returns:
            A Future representing the given call.
        """
        raise NotImplementedError()

    def map(self, fn, *iterables, timeout=None, chunksize=1):
        """Returns an iterator equivalent to map(fn, iter).

        Args:
            fn: A callable that will take as many arguments as there are
                passed iterables.
            timeout: The maximum number of seconds to wait. If None, then
                there is no limit on the wait time.
            chunksize: The size of the chunks the iterable will be broken
                into before being passed to a child process.  This argument
                is only used by ProcessPoolExecutor; it is ignored by
                ThreadPoolExecutor.

        Returns:
            An iterator equivalent to: map(func, *iterables) but the calls
            may be evaluated out-of-order.

        Raises:
            TimeoutError: If the entire result iterator could not be
                generated before the given timeout.
            Exception: If fn(*args) raises for any values.
        """
        if timeout is not None:
            end_time = timeout + time.monotonic()
        else:
            # Pystachy port: (a closure's variables are assigned before its def)
            end_time = 0.0

        # Pystachy port: zip(*iterables) is written out for up to four iterables (zip() takes no
        # starred argument), for none as the list of no future that CPython's zip() gives; more
        # iterables raise NotImplementedError, before any call
        if len(iterables) == 0:
            fs = [self.submit(fn) for _ in range(0)]
        elif len(iterables) == 1:
            fs = [self.submit(fn, arg) for arg in iterables[0]]
        elif len(iterables) == 2:
            fs = [self.submit(fn, *args) for args in zip(iterables[0], iterables[1])]
        elif len(iterables) == 3:
            fs = [self.submit(fn, *args) for args in zip(iterables[0], iterables[1], iterables[2])]
        elif len(iterables) == 4:
            fs = [self.submit(fn, *args) for args in zip(iterables[0], iterables[1], iterables[2], iterables[3])]
        else:
            raise NotImplementedError("Executor.map() of more than four iterables is not supported")

        # Yield must be hidden in closure so that the futures are submitted
        # before the first iterator value is required.
        def result_iterator():
            try:
                # reverse to keep finishing order
                fs.reverse()
                while fs:
                    # Careful not to keep a reference to the popped future
                    if timeout is None:
                        yield _result_or_cancel(fs.pop())
                    else:
                        yield _result_or_cancel(fs.pop(), end_time - time.monotonic())
            finally:
                for future in fs:
                    future.cancel()
        return result_iterator()

    def shutdown(self, wait=True, *, cancel_futures=False):
        """Clean-up the resources associated with the Executor.

        It is safe to call this method several times. Otherwise, no other
        methods can be called after this one.

        Args:
            wait: If True then shutdown will not return until all running
                futures have finished executing and the resources used by
                the executor have been reclaimed.
            cancel_futures: If True then shutdown will cancel all pending
                futures. Futures that are completed or running will not be
                cancelled.
        """
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
        return False


class BrokenExecutor(RuntimeError):
    """
    Raised when a executor has become non-functional after a severe failure.
    """
