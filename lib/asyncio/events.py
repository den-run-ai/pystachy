"""Event loop and event loop policy."""

# Contains code from https://github.com/MagicStack/uvloop/tree/v0.16.0
# SPDX-License-Identifier: PSF-2.0 AND (MIT OR Apache-2.0)
# SPDX-FileCopyrightText: Copyright (c) 2015-2021 MagicStack Inc.  http://magic.io

# Pystachy port: the loop's handles, the loop interface its futures and tasks call, and the running
# loop; no policies' child watchers, servers, sockets, subprocesses, signals or threads
# (lib/compatibility.md#asyncio)
__all__ = (
    'AbstractEventLoopPolicy',
    'AbstractEventLoop',
    'Handle', 'TimerHandle',
    'get_event_loop_policy', 'set_event_loop_policy',
    'get_event_loop', 'set_event_loop', 'new_event_loop',
    '_set_running_loop', 'get_running_loop',
    '_get_running_loop',
)

import sys
from typing import Callable


class Handle:
    """Object returned by callback registration methods."""

    # Pystachy port: the callback is a function of no arguments that calls the one registered with
    # its arguments (call_soon makes it), and its context is not kept (no contextvars)
    def __init__(self, callback: Callable[[], None], loop: "AbstractEventLoop") -> None:
        self._loop = loop
        self._callback = callback
        self._cancelled = False
        self._repr = ""

    def _repr_info(self) -> list[str]:
        info = [self.__class__.__name__]
        if self._cancelled:
            info.append('cancelled')
        return info

    def __repr__(self) -> str:
        if self._repr != "":
            return self._repr
        info = self._repr_info()
        return '<{}>'.format(' '.join(info))

    def cancel(self) -> None:
        if not self._cancelled:
            self._cancelled = True

    def cancelled(self) -> bool:
        return self._cancelled

    def _run(self) -> None:
        try:
            self._callback()
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            msg = f'Exception in callback {self!r}'
            self._loop.call_exception_handler(msg, exc)


class TimerHandle(Handle):
    """Object returned by timed callback registration methods."""

    def __init__(self, when: float, callback: Callable[[], None], loop: "AbstractEventLoop") -> None:
        super().__init__(callback, loop)
        self._when = when
        self._scheduled = False

    def _repr_info(self) -> list[str]:
        info = super()._repr_info()
        pos = 2 if self._cancelled else 1
        info.insert(pos, f'when={self._when}')
        return info

    def __lt__(self, other: "TimerHandle") -> bool:
        return self._when < other._when

    def __le__(self, other: "TimerHandle") -> bool:
        return self._when <= other._when

    def __gt__(self, other: "TimerHandle") -> bool:
        return self._when > other._when

    def __ge__(self, other: "TimerHandle") -> bool:
        return self._when >= other._when

    def cancel(self) -> None:
        if not self._cancelled:
            self._loop._timer_handle_cancelled(self)
        super().cancel()

    def when(self) -> float:
        """Return a scheduled callback time.

        The time is an absolute timestamp, using the same time
        reference as loop.time().
        """
        return self._when


class AbstractEventLoop:
    """Abstract event loop."""

    # Pystachy port: the methods that futures, tasks and the module's functions call, which
    # base_events.BaseEventLoop implements

    def run_forever(self) -> None:
        """Run the event loop until stop() is called."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop the event loop as soon as reasonable.

        Exactly how soon that is may depend on the implementation, but
        no more I/O callbacks should be scheduled.
        """
        raise NotImplementedError

    def is_running(self) -> bool:
        """Return whether the event loop is currently running."""
        raise NotImplementedError

    def is_closed(self) -> bool:
        """Returns True if the event loop was closed."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the loop.

        The loop should not be running.

        This is idempotent and irreversible.

        No other methods should be called after this one.
        """
        raise NotImplementedError

    def run_until_complete(self, future):
        """Run the event loop until a Future is done.

        Return the Future's result, or raise its exception.
        """
        raise NotImplementedError

    def create_task(self, coro, *, name: str | None = None, context=None):
        raise NotImplementedError

    def set_task_factory(self, factory) -> None:
        raise NotImplementedError

    def _eager_tasks(self) -> bool:
        # Pystachy port: whether the task factory is eager_task_factory (tasks._create_task)
        raise NotImplementedError

    def _timer_handle_cancelled(self, handle: TimerHandle) -> None:
        """Notification that a TimerHandle has been cancelled."""
        raise NotImplementedError

    def _call_handle(self, handle: Handle) -> Handle:
        # Pystachy port: call_soon() of the handle its callback is (see BaseEventLoop.call_soon)
        raise NotImplementedError

    def _call_handle_at(self, handle: TimerHandle) -> TimerHandle:
        raise NotImplementedError

    def time(self) -> float:
        raise NotImplementedError

    def get_debug(self) -> bool:
        raise NotImplementedError

    def set_debug(self, enabled: bool) -> None:
        raise NotImplementedError

    def call_exception_handler(self, message: str, exc: BaseException | None) -> None:
        # Pystachy port: the context dict's message and exception
        raise NotImplementedError

    # Pystachy port: methods that take callbacks and their arguments make the handle in this
    # class, for every loop (Handle, call_soon)
    def call_soon(self, callback, *args, context=None) -> Handle:
        def run() -> None:
            callback(*args)

        return self._call_handle(Handle(run, self))

    def call_later(self, delay: float, callback, *args, context=None) -> TimerHandle:
        """Arrange for a callback to be called at a given time.

        Return a Handle: an opaque object with a cancel() method that
        can be used to cancel the call.

        The delay can be an int or float, expressed in seconds.  It is
        always relative to the current time.

        Each callback will be called exactly once.  If two callbacks
        are scheduled for exactly the same time, it is undefined which
        will be called first.

        Any positional arguments after the callback will be passed to
        the callback when it is called.
        """
        return self.call_at(self.time() + delay, callback, *args, context=context)

    def call_at(self, when: float, callback, *args, context=None) -> TimerHandle:
        """Like call_later(), but uses an absolute time.

        Absolute time corresponds to the event loop's time() method.
        """
        def run() -> None:
            callback(*args)

        return self._call_handle_at(TimerHandle(when, run, self))


class AbstractEventLoopPolicy:
    """Abstract policy for accessing the event loop."""

    # Pystachy port: the default policy's loop for the program's one thread
    def __init__(self) -> None:
        self._loop: AbstractEventLoop | None = None
        self._set_called = False

    def get_event_loop(self) -> AbstractEventLoop:
        """Get the event loop for the current context.

        Returns an event loop object implementing the AbstractEventLoop interface,
        or raises an exception in case no event loop has been set for the
        current context and the current policy does not know how to create one.

        It should never return None."""
        loop = self._loop
        if loop is None and not self._set_called:
            loop = self.new_event_loop()
            self.set_event_loop(loop)
        if loop is None:
            raise RuntimeError('There is no current event loop in thread %r.'
                               % 'MainThread')
        return loop

    def set_event_loop(self, loop: AbstractEventLoop | None) -> None:
        """Set the event loop for the current context to loop."""
        self._set_called = True
        self._loop = loop

    def new_event_loop(self) -> AbstractEventLoop:
        """Create and return a new event loop object according to this
        policy's rules. If there's need to set this loop as the event loop for
        the current context, set_event_loop must be called explicitly."""
        return _new_loop()


# Event loop policy.  The policy itself is always global, even if the
# policy's rules say that there is an event loop per thread (or other
# notion of context).  The default policy is installed by the first
# call to get_event_loop_policy().
_event_loop_policy: AbstractEventLoopPolicy | None = None

# Pystachy port: the running loop of the program's one thread, and the class whose objects
# new_event_loop() makes (base_events sets it: it imports this module)
_running_loop: AbstractEventLoop | None = None
_loop_factory: list[Callable[[], AbstractEventLoop]] = []


def _new_loop() -> AbstractEventLoop:
    return _loop_factory[0]()


def get_running_loop() -> AbstractEventLoop:
    """Return the running event loop.  Raise a RuntimeError if there is none.

    This function is thread-specific.
    """
    # NOTE: this function is implemented in C (see _asynciomodule.c)
    loop = _get_running_loop()
    if loop is None:
        raise RuntimeError('no running event loop')
    return loop


def _get_running_loop() -> AbstractEventLoop | None:
    """Return the running event loop or None.

    This is a low-level function intended to be used by event loops.
    This function is thread-specific.
    """
    return _running_loop


def _set_running_loop(loop: AbstractEventLoop | None) -> None:
    """Set the running event loop.

    This is a low-level function intended to be used by event loops.
    This function is thread-specific.
    """
    global _running_loop
    _running_loop = loop


def get_event_loop_policy() -> AbstractEventLoopPolicy:
    """Get the current event loop policy."""
    global _event_loop_policy
    policy = _event_loop_policy
    if policy is None:
        policy = AbstractEventLoopPolicy()
        _event_loop_policy = policy
    return policy


def set_event_loop_policy(policy: AbstractEventLoopPolicy | None) -> None:
    """Set the current event loop policy.

    If policy is None, the default policy is restored."""
    global _event_loop_policy
    _event_loop_policy = policy


def get_event_loop() -> AbstractEventLoop:
    """Return an asyncio event loop.

    When called from a coroutine or a callback (e.g. scheduled with call_soon
    or similar API), this function will always return the running event loop.

    If there is no running event loop set, the function will return
    the result of `get_event_loop_policy().get_event_loop()` call.
    """
    # NOTE: this function is implemented in C (see _asynciomodule.c)
    current_loop = _get_running_loop()
    if current_loop is not None:
        return current_loop
    return get_event_loop_policy().get_event_loop()


def set_event_loop(loop: AbstractEventLoop | None) -> None:
    """Equivalent to calling get_event_loop_policy().set_event_loop(loop)."""
    get_event_loop_policy().set_event_loop(loop)


def new_event_loop() -> AbstractEventLoop:
    """Equivalent to calling get_event_loop_policy().new_event_loop()."""
    return get_event_loop_policy().new_event_loop()
