__all__ = ('Runner', 'run')

from types import TracebackType

from . import events
from . import exceptions
from . import futures
from . import tasks


# Pystachy port: the states are _State's values, str constants (no enum)
_CREATED = "created"
_INITIALIZED = "initialized"
_CLOSED = "closed"


class Runner:
    """A context manager that controls event loop life cycle.

    The context manager always creates a new event loop,
    allows to run async functions inside it,
    and properly finalizes the loop at the context manager exit.

    If debug is True, the event loop will be run in debug mode.
    If loop_factory is passed, it is used for new event loop creation.

    asyncio.run(main(), debug=True)

    is a shortcut for

    with asyncio.Runner(debug=True) as runner:
        runner.run(main())

    The run() method can be called multiple times within the runner's
    context.

    This can be useful for interactive console (e.g. IPython),
    unittest runners, console tools, -- everywhere when async code
    is called from existing sync framework and where the preferred single
    asyncio.run() call doesn't work.

    """

    # Note: the class is final, it is not intended for inheritance.

    # Pystachy port: no loop_factory (but None), contexts or SIGINT handler
    def __init__(self, *, debug: bool | None = None, loop_factory=None) -> None:
        if loop_factory is not None:
            raise NotImplementedError("Runner(loop_factory=...) is not supported")
        self._state: str = _CREATED
        self._debug = debug
        self._loop: events.AbstractEventLoop | None = None
        self._interrupt_count = 0
        self._set_event_loop = False

    def __enter__(self) -> "Runner":
        self._lazy_init()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        """Shutdown and close event loop."""
        if self._state != _INITIALIZED:
            return
        loop = self._loop
        assert loop is not None
        try:
            _cancel_all_tasks(loop)
        finally:
            if self._set_event_loop:
                events.set_event_loop(None)
            loop.close()
            self._loop = None
            self._state = _CLOSED

    def get_loop(self) -> events.AbstractEventLoop:
        """Return embedded event loop."""
        self._lazy_init()
        loop = self._loop
        assert loop is not None
        return loop

    def run(self, coro, *, context=None):
        """Run a coroutine inside the embedded event loop."""
        # Pystachy port: coro's type is a coroutine's (Task's annotation checks it)
        if events._get_running_loop() is not None:
            # fail fast with short traceback
            raise RuntimeError(
                "Runner.run() cannot be called from a running event loop")

        self._lazy_init()
        loop = self._loop
        assert loop is not None

        task = tasks._create_task(loop, coro, None)

        self._interrupt_count = 0
        return loop.run_until_complete(task)

    def _lazy_init(self) -> None:
        if self._state == _CLOSED:
            raise RuntimeError("Runner is closed")
        if self._state == _INITIALIZED:
            return
        loop = events.new_event_loop()
        self._loop = loop
        if not self._set_event_loop:
            # Call set_event_loop only once to avoid calling
            # attach_loop multiple times on child watchers
            events.set_event_loop(loop)
            self._set_event_loop = True
        debug = self._debug
        if debug is not None:
            loop.set_debug(debug)
        self._state = _INITIALIZED


def run(main, *, debug: bool | None = None, loop_factory=None):
    """Execute the coroutine and return the result.

    This function runs the passed coroutine, taking care of
    managing the asyncio event loop, finalizing asynchronous
    generators and closing the default executor.

    This function cannot be called when another asyncio event loop is
    running in the same thread.

    If debug is True, the event loop will be run in debug mode.
    If loop_factory is passed, it is used for new event loop creation.

    This function always creates a new event loop and closes it at the end.
    It should be used as a main entry point for asyncio programs, and should
    ideally only be called once.

    The executor is given a timeout duration of 5 minutes to shutdown.
    If the executor hasn't finished within that duration, a warning is
    emitted and the executor is closed.

    Example:

        async def main():
            await asyncio.sleep(1)
            print('hello')

        asyncio.run(main())
    """
    if events._get_running_loop() is not None:
        # fail fast with short traceback
        raise RuntimeError(
            "asyncio.run() cannot be called from a running event loop")

    with Runner(debug=debug, loop_factory=loop_factory) as runner:
        return runner.run(main)


def _cancel_all_tasks(loop: events.AbstractEventLoop) -> None:
    to_cancel = tasks.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    # Pystachy port: a future done once they are, for gather(*to_cancel, return_exceptions=True)
    loop.run_until_complete(_all_done(loop, to_cancel))

    for task in to_cancel:
        if task.cancelled():
            continue
        exc = task.exception()
        if exc is not None:
            loop.call_exception_handler(
                'unhandled exception during asyncio.run() shutdown', exc)


def _all_done(loop: events.AbstractEventLoop, fs: list[futures._FutureBase]) -> futures.Future[None]:
    # Pystachy port: a Future[None] done once all of fs are
    outer: futures.Future[None] = futures.Future(loop=loop)
    left = [len(fs)]

    def one() -> None:
        left[0] -= 1
        if left[0] == 0 and not outer.done():
            outer.set_result(None)

    for f in fs:
        f._add_callback(one)
    return outer
