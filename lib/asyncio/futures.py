"""A Future class similar to the one in PEP 3148."""

__all__ = (
    'Future', 'isfuture',
)

# Pystachy port: concurrent.futures (wrap_future), contextvars, logging and GenericAlias are not
# imported: no thread pools, contexts or debug logging (lib/compatibility.md#asyncio)
from typing import Callable, Generic, TypeVar

from . import base_futures
from . import events
from . import exceptions

T = TypeVar("T")

_PENDING = base_futures._PENDING
_CANCELLED = base_futures._CANCELLED
_FINISHED = base_futures._FINISHED


# Pystachy port: what a Future of any result type has, and awaiting one leaves for the task that
# awaits it (see Future.__await__): a Future[T] (and a Task[T]) derives from it, so that a loop, a
# task, gather() and a TaskGroup hold futures of different result types. Its callbacks are
# functions of no arguments that call the one registered with the future (add_done_callback)
class _FutureBase:
    """This class is *almost* compatible with concurrent.futures.Future.

    Differences:

    - This class is not thread-safe.

    - result() and exception() do not take a timeout argument and
      raise an exception when the future isn't done yet.

    - Callbacks registered with add_done_callback() are always called
      via the event loop's call_soon().

    - This class is not compatible with the wait() and as_completed()
      methods in the concurrent.futures package.

    (In Python 3.4 or later we may be able to unify the implementations.)
    """

    def __init__(self, loop: events.AbstractEventLoop | None) -> None:
        # Class variables serving as defaults for instance variables (Pystachy port: set here).
        self._state: str = _PENDING
        self._exception: BaseException | None = None
        self._cancel_message: str | None = None
        # A saved CancelledError for later chaining as an exception context.
        self._cancelled_exc: BaseException | None = None
        # This field is used for a dual purpose:
        # - Its presence is a marker to declare that a class implements
        #   the Future protocol (i.e. is intended to be duck-type compatible).
        #   The value must also be not-None, to enable a subclass to declare
        #   that it is not compatible by setting this to None.
        # - It is set by __iter__() below so that Task._step() can tell
        #   the difference between
        #   `await Future()` or`yield from Future()` (correct) vs.
        #   `yield Future()` (incorrect).
        self._asyncio_future_blocking = False
        self.__log_traceback = False
        if loop is None:
            self._loop = events.get_event_loop()
        else:
            self._loop = loop
        self._callbacks: list[Callable[[], None]] = []

    def get_loop(self) -> events.AbstractEventLoop:
        """Return the event loop the Future is bound to."""
        return self._loop

    def _make_cancelled_error(self) -> BaseException:
        """Create the CancelledError to raise if the Future is cancelled.

        This should only be called once when handling a cancellation since
        it erases the saved context exception value.
        """
        exc = self._cancelled_exc
        if exc is not None:
            self._cancelled_exc = None
            return exc

        msg = self._cancel_message
        if msg is None:
            return exceptions._as_exception(exceptions.CancelledError())
        return exceptions._as_exception(exceptions.CancelledError(msg))

    def cancel(self, msg: str | None = None) -> bool:
        """Cancel the future and schedule callbacks.

        If the future is already done or cancelled, return False.  Otherwise,
        change the future's state to cancelled, schedule the callbacks and
        return True.
        """
        self.__log_traceback = False
        if self._state != _PENDING:
            return False
        self._state = _CANCELLED
        self._cancel_message = msg
        self._schedule_callbacks()
        return True

    def _schedule_callbacks(self) -> None:
        """Internal: Ask the event loop to call all callbacks.

        The callbacks are scheduled to be called as soon as possible. Also
        clears the callback list.
        """
        callbacks = self._callbacks[:]
        if not callbacks:
            return

        self._callbacks.clear()
        for callback in callbacks:
            self._loop._call_handle(events.Handle(callback, self._loop))

    def cancelled(self) -> bool:
        """Return True if the future was cancelled."""
        return self._state == _CANCELLED

    # Don't implement running(); see http://bugs.python.org/issue18699

    def done(self) -> bool:
        """Return True if the future is done.

        Done means either that a result / exception are available, or that the
        future was cancelled.
        """
        return self._state != _PENDING

    def _check_result(self) -> None:
        # Pystachy port: result()'s checks, which raise what it raises but for its value
        if self._state == _CANCELLED:
            raise self._make_cancelled_error()
        if self._state != _FINISHED:
            raise exceptions.InvalidStateError('Result is not ready.')
        self.__log_traceback = False
        exc = self._exception
        if exc is not None:
            raise exc

    def exception(self) -> BaseException | None:
        """Return the exception that was set on this future.

        The exception (or None if no exception was set) is returned only if
        the future is done.  If the future has been cancelled, raises
        CancelledError.  If the future isn't done yet, raises
        InvalidStateError.
        """
        if self._state == _CANCELLED:
            raise self._make_cancelled_error()
        if self._state != _FINISHED:
            raise exceptions.InvalidStateError('Exception is not set.')
        self.__log_traceback = False
        return self._exception

    def _add_callback(self, callback: Callable[[], None]) -> None:
        # Pystachy port: add_done_callback() of a function that calls the one registered
        if self._state != _PENDING:
            self._loop._call_handle(events.Handle(callback, self._loop))
        else:
            self._callbacks.append(callback)

    def _remove_callback(self, callback: Callable[[], None]) -> None:
        # Pystachy port: remove_done_callback() of a function _add_callback() was given
        self._callbacks = [c for c in self._callbacks if c is not callback]

    # Pystachy port: Task's cancelling() and uncancel(), which current_task() and a TaskGroup's
    # parent task, futures of any type, call: a Future has no such attribute, as in CPython, but
    # where it is called (lib/compatibility.md#asyncio)
    def cancelling(self) -> int:
        raise AttributeError(f"'{type(self).__name__}' object has no attribute 'cancelling'")

    def uncancel(self) -> int:
        raise AttributeError(f"'{type(self).__name__}' object has no attribute 'uncancel'")

    def set_exception(self, exception: BaseException) -> None:
        """Mark the future done and set an exception.

        If the future is already done when this method is called, raises
        InvalidStateError.
        """
        if self._state != _PENDING:
            raise exceptions.InvalidStateError(f'{self._state}: {self!r}')
        if isinstance(exception, StopIteration):
            new_exc = RuntimeError("StopIteration interacts badly with "
                                   "generators and cannot be raised into a "
                                   "Future")
            exception = exceptions._as_exception(new_exc)
        self._exception = exception
        self._state = _FINISHED
        self._schedule_callbacks()
        self.__log_traceback = True

    def _repr_result(self) -> str:
        # Pystachy port: the result's repr for _future_repr_info, of a Future[T]
        return ""

    def __repr__(self) -> str:
        return base_futures._future_repr(self)


# Pystachy port: awaiting a pending future records it here for the task that runs the awaiting
# coroutine (Task.__step), and yields None: every awaitable of asyncio yields None, where
# CPython's future yields itself, so that a coroutine's yield type is the same everywhere
_waiting_on: list[_FutureBase] = []


class Future(_FutureBase, Generic[T]):
    """This class is *almost* compatible with concurrent.futures.Future.

    Differences:

    - This class is not thread-safe.

    - result() and exception() do not take a timeout argument and
      raise an exception when the future isn't done yet.

    - Callbacks registered with add_done_callback() are always called
      via the event loop's call_soon().

    - This class is not compatible with the wait() and as_completed()
      methods in the concurrent.futures package.

    (In Python 3.4 or later we may be able to unify the implementations.)
    """

    def __init__(self, *, loop: events.AbstractEventLoop | None = None) -> None:
        """Initialize the future.

        The optional event_loop argument allows explicitly setting the event
        loop object used by the future. If it's not provided, the future uses
        the default event loop.
        """
        super().__init__(loop)
        # Pystachy port: the result, once set, is the list's one item (a T, without a None of its own)
        self._result: list[T] = []

    def result(self) -> T:
        """Return the result this future represents.

        If the future has been cancelled, raises CancelledError.  If the
        future's result isn't yet available, raises InvalidStateError.  If
        the future is done and has an exception set, this exception is raised.
        """
        self._check_result()
        return self._result[0]

    def add_done_callback(self, fn, *, context=None) -> None:
        """Add a callback to be run when the future becomes done.

        The callback is called with a single argument - the future object. If
        the future is already done when this is called, the callback is
        scheduled with call_soon.
        """
        def callback() -> None:
            fn(self)

        self._add_callback(callback)

    # So-called internal methods (note: no set_running_or_notify_cancel()).

    def set_result(self, result: T) -> None:
        """Mark the future done and set its result.

        If the future is already done when this method is called, raises
        InvalidStateError.
        """
        if self._state != _PENDING:
            raise exceptions.InvalidStateError(f'{self._state}: {self!r}')
        self._result.append(result)
        self._state = _FINISHED
        self._schedule_callbacks()

    def _repr_result(self) -> str:
        return repr(self._result[0])

    def __await__(self):
        if not self.done():
            self._asyncio_future_blocking = True
            _waiting_on.append(self)
            yield None  # This tells Task to wait for completion.
        if not self.done():
            raise RuntimeError("await wasn't used with future")
        return self.result()  # May raise too.


# Needed for testing purposes.
_PyFuture = Future


# Pystachy port: whether obj is a Future (or a Task), of any result type; no duck-typed futures
def isfuture(obj) -> bool:
    """Check for a Future.

    This returns True when obj is a Future instance or is advertising
    itself as duck-type compatible by setting _asyncio_future_blocking.
    See comment in Future for more details.
    """
    return isinstance(obj, _FutureBase)


def _get_loop(fut: _FutureBase) -> events.AbstractEventLoop:
    return fut.get_loop()


def _set_result_unless_cancelled(fut, result) -> None:
    """Helper setting the result only if the future was not cancelled."""
    if fut.cancelled():
        return
    fut.set_result(result)
