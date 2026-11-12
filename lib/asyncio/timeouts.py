from types import TracebackType
from typing import Optional

from . import events
from . import exceptions
from . import futures
from . import tasks


__all__ = (
    "Timeout",
    "timeout",
    "timeout_at",
)


# Pystachy port: the states are _State's values, str constants (no enum)
_CREATED = "created"
_ENTERED = "active"
_EXPIRING = "expiring"
_EXPIRED = "expired"
_EXITED = "finished"


# Pystachy port: not decorated @final (a class decorator is not supported)
class Timeout:
    """Asynchronous context manager for cancelling overdue coroutines.

    Use `timeout()` or `timeout_at()` rather than instantiating this class
    directly.
    """

    def __init__(self, when: Optional[float]) -> None:
        """Schedule a timeout that will trigger at a given loop time.

        - If `when` is `None`, the timeout will never trigger.
        - If `when < loop.time()`, the timeout will trigger on the next
          iteration of the event loop.
        """
        self._state: str = _CREATED

        self._timeout_handler: Optional[events.Handle] = None
        self._task: Optional[futures._FutureBase] = None
        self._when = when
        self._cancelling = 0

    def when(self) -> Optional[float]:
        """Return the current deadline."""
        return self._when

    def reschedule(self, when: Optional[float]) -> None:
        """Reschedule the timeout."""
        if self._state != _ENTERED:
            if self._state == _CREATED:
                raise RuntimeError("Timeout has not been entered")
            raise RuntimeError(
                f"Cannot change state of {self._state} Timeout",
            )

        self._when = when

        handler = self._timeout_handler
        if handler is not None:
            handler.cancel()

        if when is None:
            self._timeout_handler = None
        else:
            loop = events.get_running_loop()
            if when <= loop.time():
                self._timeout_handler = loop.call_soon(self._on_timeout)
            else:
                self._timeout_handler = loop.call_at(when, self._on_timeout)

    def expired(self) -> bool:
        """Is timeout expired during execution?"""
        return self._state in (_EXPIRING, _EXPIRED)

    def __repr__(self) -> str:
        info = ['']
        if self._state == _ENTERED:
            w = self._when
            when = str(round(w, 3)) if w is not None else "None"
            info.append(f"when={when}")
        info_str = ' '.join(info)
        return f"<Timeout [{self._state}]{info_str}>"

    async def __aenter__(self) -> "Timeout":
        if self._state != _CREATED:
            raise RuntimeError("Timeout has already been entered")
        task = tasks.current_task()
        if task is None:
            raise RuntimeError("Timeout should be used inside a task")
        self._state = _ENTERED
        self._task = task
        self._cancelling = task.cancelling()
        self.reschedule(self._when)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        assert self._state in (_ENTERED, _EXPIRING)

        handler = self._timeout_handler
        if handler is not None:
            handler.cancel()
            self._timeout_handler = None

        if self._state == _EXPIRING:
            self._state = _EXPIRED
            task = self._task
            assert task is not None
            if task.uncancel() <= self._cancelling and exc_val is not None:
                # Since there are no new cancel requests, we're
                # handling this.
                # Pystachy port: no exception contexts, which CPython's
                # _insert_timeout_error() would chain
                if isinstance(exc_val, exceptions.CancelledError):
                    raise TimeoutError from exc_val
        elif self._state == _ENTERED:
            self._state = _EXITED

        return None

    def _on_timeout(self) -> None:
        assert self._state == _ENTERED
        task = self._task
        assert task is not None
        task.cancel()
        self._state = _EXPIRING
        # drop the reference early
        self._timeout_handler = None


def timeout(delay: Optional[float]) -> Timeout:
    """Timeout async context manager.

    Useful in cases when you want to apply timeout logic around block
    of code or in cases when asyncio.wait_for is not suitable. For example:

    >>> async with asyncio.timeout(10):  # 10 seconds timeout
    ...     await long_running_task()


    delay - value in seconds or None to disable timeout logic

    long_running_task() is interrupted by raising asyncio.CancelledError,
    the top-most affected timeout() context manager converts CancelledError
    into TimeoutError.
    """
    loop = events.get_running_loop()
    return Timeout(loop.time() + delay if delay is not None else None)


def timeout_at(when: Optional[float]) -> Timeout:
    """Schedule the timeout at absolute time.

    Like timeout() but argument gives absolute time in the same clock system
    as loop.time().

    Please note: it is not POSIX time but a time with
    undefined starting base, e.g. the time of the system power on.

    >>> async with asyncio.timeout_at(loop.time() + 10):
    ...     await long_running_task()


    when - a deadline when timeout occurs or None to disable timeout logic

    long_running_task() is interrupted by raising asyncio.CancelledError,
    the top-most affected timeout() context manager converts CancelledError
    into TimeoutError.
    """
    return Timeout(when)
