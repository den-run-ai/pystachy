# Adapted with permission from the EdgeDB project;
# license: PSFL.


__all__ = ("TaskGroup",)

from types import TracebackType

from . import events
from . import exceptions
from . import futures
from . import tasks


class TaskGroup:
    """Asynchronous context manager for managing groups of tasks.

    Example use:

        async with asyncio.TaskGroup() as group:
            task1 = group.create_task(some_coroutine(...))
            task2 = group.create_task(other_coroutine(...))
        print("Both tasks have completed now.")

    All tasks are awaited when the context manager exits.

    Any exceptions other than `asyncio.CancelledError` raised within
    a task will cancel all remaining tasks and wait for them to exit.
    The exceptions are then combined and raised as an `ExceptionGroup`.
    """
    # Pystachy port: exception groups are not supported: where tasks fail, the TaskGroup raises
    # the first one's exception, or its base error (lib/compatibility.md#asyncio)
    def __init__(self) -> None:
        self._entered = False
        self._exiting = False
        self._aborting = False
        self._loop: events.AbstractEventLoop | None = None
        self._parent_task: futures._FutureBase | None = None
        self._parent_cancel_requested = False
        # Pystachy port: a dict whose keys are the tasks, as a set of them
        self._tasks: dict[futures._FutureBase, bool] = {}
        self._errors: list[BaseException] = []
        self._base_error: BaseException | None = None
        self._on_completed_fut: futures.Future[bool] | None = None

    def __repr__(self) -> str:
        info = ['']
        if self._tasks:
            info.append(f'tasks={len(self._tasks)}')
        if self._errors:
            info.append(f'errors={len(self._errors)}')
        if self._aborting:
            info.append('cancelling')
        elif self._entered:
            info.append('entered')

        info_str = ' '.join(info)
        return f'<TaskGroup{info_str}>'

    async def __aenter__(self) -> "TaskGroup":
        if self._entered:
            raise RuntimeError(
                f"TaskGroup {self!r} has already been entered")
        if self._loop is None:
            self._loop = events.get_running_loop()
        self._parent_task = tasks.current_task(self._loop)
        if self._parent_task is None:
            raise RuntimeError(
                f'TaskGroup {self!r} cannot determine the parent task')
        self._entered = True

        return self

    async def __aexit__(self, et: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        try:
            await self._aexit(et is not None, exc)
        finally:
            # Exceptions are heavy objects that can have object
            # cycles (bad for GC); let's not keep a reference to
            # a bunch of them. It would be nicer to use a try/finally
            # in __aexit__ directly but that introduced some diff noise
            self._parent_task = None
            self._errors = []
            self._base_error = None

    async def _aexit(self, raised: bool, exc: BaseException | None) -> None:
        self._exiting = True

        if (exc is not None and
                self._is_base_error(exc) and
                self._base_error is None):
            self._base_error = exc

        propagate_cancellation_error: BaseException | None = None
        if exc is not None and isinstance(exc, exceptions.CancelledError):
            propagate_cancellation_error = exc

        if raised:
            if not self._aborting:
                # Our parent task is being cancelled:
                #
                #    async with TaskGroup() as g:
                #        g.create_task(...)
                #        await ...  # <- CancelledError
                #
                # or there's an exception in "async with":
                #
                #    async with TaskGroup() as g:
                #        g.create_task(...)
                #        1 / 0
                #
                self._abort()

        # We use while-loop here because "self._on_completed_fut"
        # can be cancelled multiple times if our parent task
        # is being cancelled repeatedly (or even once, when
        # our own cancellation is already in progress)
        loop = self._loop
        assert loop is not None
        while self._tasks:
            fut: futures.Future[bool] = futures.Future(loop=loop)
            self._on_completed_fut = fut

            try:
                await fut
            except exceptions.CancelledError:
                if not self._aborting:
                    # Our parent task is being cancelled:
                    #
                    #    async def wrapper():
                    #        async with TaskGroup() as g:
                    #            g.create_task(foo)
                    #
                    # "wrapper" is being cancelled while "foo" is
                    # still running.
                    propagate_cancellation_error = fut._make_cancelled_error()
                    self._abort()

            self._on_completed_fut = None

        assert not self._tasks

        base_error = self._base_error
        if base_error is not None:
            raise base_error

        parent = self._parent_task
        assert parent is not None
        # If we wanted to raise an error, it would have been done explicitly above.
        if self._parent_cancel_requested:
            # If this flag is set we *must* call uncancel().
            if parent.uncancel() == 0:
                # If there are no pending cancellations left,
                # don't propagate CancelledError.
                propagate_cancellation_error = None

        # Propagate CancelledError if there is one, except if there
        # are other errors -- those have priority.
        if propagate_cancellation_error is not None and not self._errors:
            raise propagate_cancellation_error

        if raised and exc is not None and not isinstance(exc, exceptions.CancelledError):
            self._errors.append(exc)

        if self._errors:
            # If the parent task is being cancelled from the outside
            # of the taskgroup, un-cancel and re-cancel the parent task,
            # which will keep the cancel count stable.
            if parent.cancelling():
                parent.uncancel()
                parent.cancel()
            # Pystachy port: the first error, where CPython raises
            # BaseExceptionGroup('unhandled errors in a TaskGroup', self._errors)
            raise self._errors[0]

    def create_task(self, coro, *, name: str | None = None, context=None):
        """Create a new task in this group and return it.

        Similar to `asyncio.create_task`.
        """
        if not self._entered:
            coro.close()
            raise RuntimeError(f"TaskGroup {self!r} has not been entered")
        if self._exiting and not self._tasks:
            coro.close()
            raise RuntimeError(f"TaskGroup {self!r} is finished")
        if self._aborting:
            coro.close()
            raise RuntimeError(f"TaskGroup {self!r} is shutting down")
        loop = self._loop
        assert loop is not None
        task = tasks._create_task(loop, coro, name)

        # Always schedule the done callback even if the task is
        # already done (e.g. if the coro was able to complete eagerly),
        # otherwise if the task completes with an exception then it will cancel
        # the current task too early. gh-128550, gh-128588
        self._tasks[task] = True
        task.add_done_callback(self._on_task_done)
        return task

    # Since Python 3.8 Tasks propagate all exceptions correctly,
    # except for KeyboardInterrupt and SystemExit which are
    # still considered special.

    def _is_base_error(self, exc: BaseException) -> bool:
        return isinstance(exc, (SystemExit, KeyboardInterrupt))

    def _abort(self) -> None:
        self._aborting = True

        for t in self._tasks:
            if not t.done():
                t.cancel()

    def _on_task_done(self, task: futures._FutureBase) -> None:
        self._tasks.pop(task, False)

        fut = self._on_completed_fut
        if fut is not None and not self._tasks:
            if not fut.done():
                fut.set_result(True)

        if task.cancelled():
            return

        exc = task.exception()
        if exc is None:
            return

        self._errors.append(exc)
        if self._is_base_error(exc) and self._base_error is None:
            self._base_error = exc

        parent = self._parent_task
        assert parent is not None
        loop = self._loop
        assert loop is not None
        if parent.done():
            # Not sure if this case is possible, but we want to handle
            # it anyways.
            loop.call_exception_handler(
                f'Task {task!r} has errored out but its parent '
                f'task {parent} is already completed', exc)
            return

        if not self._aborting and not self._parent_cancel_requested:
            # If parent task *is not* being cancelled, it means that we want
            # to manually cancel it to abort whatever is being run right now
            # in the TaskGroup.  But we want to mark parent task as
            # "not cancelled" later in __aexit__.  Example situation that
            # we need to handle:
            #
            #    async def foo():
            #        try:
            #            async with TaskGroup() as g:
            #                g.create_task(crash_soon())
            #                await something  # <- this needs to be canceled
            #                                 #    by the TaskGroup, e.g.
            #                                 #    foo() needs to be cancelled
            #        except Exception:
            #            # Ignore any exceptions raised in the TaskGroup
            #            pass
            #        await something_else     # this line has to be called
            #                                 # after TaskGroup is finished.
            self._abort()
            self._parent_cancel_requested = True
            parent.cancel()
