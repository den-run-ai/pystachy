"""Base implementation of event loop.

The event loop can be broken up into a multiplexer (the part
responsible for notifying us of I/O events) and the event loop proper,
which wraps a multiplexer with functionality for scheduling callbacks,
immediately or at a given time in the future.

Whenever a public API takes a callback, subsequent positional
arguments will be passed to the callback if/when it is called.  This
avoids the proliferation of trivial lambdas implementing closures.
Keyword arguments for the callback are not supported; this is a
conscious design decision, leaving the door open for keyword arguments
to modify the meaning of the API call itself.
"""

# Pystachy port: the event loop proper, without a multiplexer: when nothing is ready, it sleeps
# until its next timer with time.sleep(). No sockets, transports, servers, subprocesses, signals,
# executors, threads or async generator hooks (lib/compatibility.md#asyncio)
import heapq
import sys
import time

from . import events
from . import futures
from . import tasks


__all__ = 'BaseEventLoop',


# Minimum number of _scheduled timer handles before cleanup of
# cancelled handles is performed.
_MIN_SCHEDULED_TIMER_HANDLES = 100

# Minimum fraction of _scheduled timer handles that are cancelled
# before cleanup of cancelled handles is performed.
_MIN_CANCELLED_TIMER_HANDLES_FRACTION = 0.5


# Maximum timeout passed to select to avoid OS limitations
MAXIMUM_SELECT_TIMEOUT = 24 * 3600


def _run_until_complete_cb(fut: futures._FutureBase) -> None:
    if not fut.cancelled():
        exc = fut.exception()
        if isinstance(exc, (SystemExit, KeyboardInterrupt)):
            # Issue #22429: run_forever() already finished, no need to
            # stop it.
            return
    futures._get_loop(fut).stop()


class BaseEventLoop(events.AbstractEventLoop):

    def __init__(self) -> None:
        self._timer_cancelled_count = 0
        self._closed = False
        self._stopping = False
        # Pystachy port: the ready handles, a list whose run takes the handles ready as it begins
        self._ready: list[events.Handle] = []
        self._scheduled: list[events.TimerHandle] = []
        self._clock_resolution = 1e-09  # (time.get_clock_info('monotonic').resolution on Linux)
        self._running = False
        self._debug = False
        # Pystachy port: whether eager_task_factory is the task factory (set_task_factory)
        self._eager = False

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} running={self.is_running()} '
            f'closed={self.is_closed()} debug={self.get_debug()}>'
        )

    # Pystachy port: no create_future(), whose Future's result type nothing would bind: make one
    # with asyncio.Future(loop=loop), annotated with it (f: asyncio.Future[int] = ...)

    def create_task(self, coro, *, name: str | None = None, context=None):
        """Schedule a coroutine object.

        Return a task object.
        """
        return tasks._create_task(self, coro, name)

    def _eager_tasks(self) -> bool:
        return self._eager

    def set_task_factory(self, factory) -> None:
        """Set a task factory that will be used by loop.create_task().

        If factory is None the default task factory will be set.

        If factory is a callable, it should have a signature matching
        '(loop, coro, **kwargs)', where 'loop' will be a reference to the active
        event loop, 'coro' will be a coroutine object, and **kwargs will be
        arbitrary keyword arguments that should be passed on to Task.
        The callable must return a Task.
        """
        # Pystachy port: None or tasks.eager_task_factory; a factory of the program's is not supported
        if factory is None:
            self._eager = False
        elif factory is tasks.eager_task_factory:
            self._eager = True
        else:
            raise NotImplementedError('a task factory other than asyncio.eager_task_factory is not supported')

    def _check_closed(self) -> None:
        if self._closed:
            raise RuntimeError('Event loop is closed')

    def _check_running(self) -> None:
        if self.is_running():
            raise RuntimeError('This event loop is already running')
        if events._get_running_loop() is not None:
            raise RuntimeError(
                'Cannot run the event loop while another loop is running')

    def _run_forever_setup(self) -> None:
        """Prepare the run loop to process events.

        This method exists so that custom event loop subclasses (e.g., event loops
        that integrate a GUI event loop with Python's event loop) have access to all the
        loop setup logic.
        """
        self._check_closed()
        self._check_running()
        self._running = True
        events._set_running_loop(self)

    def _run_forever_cleanup(self) -> None:
        """Clean up after an event loop finishes the looping over events.

        This method exists so that custom event loop subclasses (e.g., event loops
        that integrate a GUI event loop with Python's event loop) have access to all the
        loop cleanup logic.
        """
        self._stopping = False
        self._running = False
        events._set_running_loop(None)

    def run_forever(self) -> None:
        """Run until stop() is called."""
        self._run_forever_setup()
        try:
            while True:
                self._run_once()
                if self._stopping:
                    break
        finally:
            self._run_forever_cleanup()

    def run_until_complete(self, future):
        """Run until the Future is done.

        If the argument is a coroutine, it is wrapped in a Task.

        WARNING: It would be disastrous to call run_until_complete()
        with the same coroutine twice -- it would wrap it in two
        different Tasks and that can't be good.

        Return the Future's result, or raise its exception.
        """
        self._check_closed()
        self._check_running()

        new_task = not futures.isfuture(future)
        fut = tasks.ensure_future(future, loop=self)

        def done() -> None:
            _run_until_complete_cb(fut)

        fut._add_callback(done)
        try:
            self.run_forever()
        except BaseException:
            if new_task and fut.done() and not fut.cancelled():
                # The coroutine raised a BaseException. Consume the exception
                # to not log a warning, the caller doesn't have access to the
                # local task.
                fut.exception()
            raise
        finally:
            fut._remove_callback(done)
        if not fut.done():
            raise RuntimeError('Event loop stopped before Future completed.')

        return fut.result()

    def stop(self) -> None:
        """Stop running the event loop.

        Every callback already scheduled will still run.  This simply
        informs run_forever to stop looping after a complete iteration.
        """
        self._stopping = True

    def close(self) -> None:
        """Close the event loop.

        This clears the queues and shuts down the executor,
        but does not wait for the executor to finish.

        The event loop must not be running.
        """
        if self.is_running():
            raise RuntimeError("Cannot close a running event loop")
        if self._closed:
            return
        self._closed = True
        self._ready.clear()
        self._scheduled.clear()

    def is_closed(self) -> bool:
        """Returns True if the event loop was closed."""
        return self._closed

    def is_running(self) -> bool:
        """Returns True if the event loop is running."""
        return self._running

    def time(self) -> float:
        """Return the time according to the event loop's clock.

        This is a float expressed in seconds since an epoch, but the
        epoch, precision, accuracy and drift are unspecified and may
        differ per event loop.
        """
        return time.monotonic()

    def _call_handle_at(self, timer: events.TimerHandle) -> events.TimerHandle:
        # Pystachy port: call_at() of the handle that call_at() in events.AbstractEventLoop makes
        self._check_closed()
        heapq.heappush(self._scheduled, timer)
        timer._scheduled = True
        return timer

    def _call_handle(self, handle: events.Handle) -> events.Handle:
        """Schedule a callback to be called as soon as possible.

        This operates as a FIFO queue: callbacks are called in the
        order in which they are registered.  Each callback will be
        called exactly once.

        Any positional arguments after the callback will be passed to
        the callback when it is called.
        """
        # Pystachy port: call_soon() of the handle that call_soon() in events.AbstractEventLoop makes
        self._check_closed()
        self._ready.append(handle)
        return handle

    def get_debug(self) -> bool:
        return self._debug

    def set_debug(self, enabled: bool) -> None:
        self._debug = enabled

    def default_exception_handler(self, message: str, exception: BaseException | None) -> None:
        """Default exception handler.

        This is called when an exception occurs and no exception
        handler is set, and can be called by a custom exception
        handler that wants to defer to the default behavior.

        This default handler logs the error message and other
        context-dependent information.  In debug mode, a truncated
        stack trace is also appended showing where the given object
        (e.g. a handle or future or task) was created, if any.

        The context parameter has the same meaning as in
        `call_exception_handler()`.
        """
        # Pystachy port: the message and the exception's last traceback line, on stderr, where
        # logging's would print the traceback
        if not message:
            message = 'Unhandled exception in event loop'
        if exception is not None:
            message += f'\n{type(exception).__name__}: {exception}'
        print(message, file=sys.stderr)

    def call_exception_handler(self, message: str, exc: BaseException | None) -> None:
        """Call the current event loop's exception handler.

        The context argument is a dict containing the following keys:

        - 'message': Error message;
        - 'exception' (optional): Exception object;

        Note: do not overload this method in an event loop subclass.
        For custom exception handling, use the
        `set_exception_handler()` method.
        """
        # Pystachy port: the context's message and exception; no custom handlers
        self.default_exception_handler(message, exc)

    def _timer_handle_cancelled(self, handle: events.TimerHandle) -> None:
        """Notification that a TimerHandle has been cancelled."""
        if handle._scheduled:
            self._timer_cancelled_count += 1

    def _run_once(self) -> None:
        """Run one full iteration of the event loop.

        This calls all currently ready callbacks, polls for I/O,
        schedules the resulting callbacks, and finally schedules
        'call_later' callbacks.
        """

        sched_count = len(self._scheduled)
        if (sched_count > _MIN_SCHEDULED_TIMER_HANDLES and
            self._timer_cancelled_count / sched_count >
                _MIN_CANCELLED_TIMER_HANDLES_FRACTION):
            # Remove delayed calls that were cancelled if their number
            # is too high
            new_scheduled: list[events.TimerHandle] = []
            for timer in self._scheduled:
                if timer._cancelled:
                    timer._scheduled = False
                else:
                    new_scheduled.append(timer)

            heapq.heapify(new_scheduled)
            self._scheduled = new_scheduled
            self._timer_cancelled_count = 0
        else:
            # Remove delayed calls that were cancelled from head of queue.
            while self._scheduled and self._scheduled[0]._cancelled:
                self._timer_cancelled_count -= 1
                timer = heapq.heappop(self._scheduled)
                timer._scheduled = False

        timeout = -1.0  # (Pystachy port: None)
        if self._ready or self._stopping:
            timeout = 0.0
        elif self._scheduled:
            # Compute the desired timeout.
            timeout = self._scheduled[0]._when - self.time()
            if timeout > MAXIMUM_SELECT_TIMEOUT:
                timeout = float(MAXIMUM_SELECT_TIMEOUT)
            elif timeout < 0:
                timeout = 0.0

        # Pystachy port: no selector: wait for the next timer; with nothing ready or scheduled,
        # CPython's selector would wait for I/O that this loop does not have
        if timeout < 0:
            raise RuntimeError('Event loop has nothing ready or scheduled: it would wait forever (no I/O, signals or threads in Pystachy)')
        if timeout > 0:
            time.sleep(timeout)

        # Handle 'later' callbacks that are ready.
        end_time = self.time() + self._clock_resolution
        while self._scheduled:
            timer = self._scheduled[0]
            if timer._when >= end_time:
                break
            timer = heapq.heappop(self._scheduled)
            timer._scheduled = False
            self._ready.append(timer)

        # This is the only place where callbacks are actually *called*.
        # All other places just add them to ready.
        # Note: We run all currently scheduled callbacks, but not any
        # callbacks scheduled by callbacks run this time around --
        # they will be run the next time (after another I/O poll).
        # Use an idiom that is thread-safe without using locks.
        ready = self._ready
        self._ready = []
        for handle in ready:
            if handle._cancelled:
                continue
            handle._run()


def _new_base_loop() -> events.AbstractEventLoop:
    return BaseEventLoop()


events._loop_factory.append(_new_base_loop)  # (Pystachy port: new_event_loop()'s loop)
