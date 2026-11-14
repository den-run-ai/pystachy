"""Support for tasks, coroutines and the scheduler."""

# Pystachy port: Task, create_task(), sleep(), gather(), ensure_future(), wait_for(), current_task(),
# all_tasks() and the eager task factory; no wait(), as_completed(), shield(),
# run_coroutine_threadsafe() or custom task factories (lib/compatibility.md#asyncio)
__all__ = (
    'Task', 'create_task',
    'wait_for', 'sleep',
    'gather', 'ensure_future',
    'current_task', 'all_tasks',
    'eager_task_factory',
    '_register_task', '_unregister_task', '_enter_task', '_leave_task',
)

import math
import types
from typing import Coroutine, TypeVar

from . import base_futures
from . import events
from . import exceptions
from . import futures
from . import timeouts

T = TypeVar("T")

# Helper to generate new task names
# Pystachy port: a counter (the program has one thread)
_task_name_counter = [0]


def current_task(loop: events.AbstractEventLoop | None = None) -> futures._FutureBase | None:
    """Return a currently executed task."""
    if loop is None:
        loop = events.get_running_loop()
    return _current_tasks.get(loop, None)


def all_tasks(loop: events.AbstractEventLoop | None = None) -> list[futures._FutureBase]:
    """Return a set of all tasks for the loop."""
    # Pystachy port: a list of the tasks registered (_register_task) and not done
    if loop is None:
        loop = events.get_running_loop()
    return [t for t in _scheduled_tasks
            if futures._get_loop(t) is loop and not t.done()]


class Task(futures.Future[T]):  # Inherit Python Task implementation
                                # from a Python Future implementation.

    """A coroutine wrapped in a Future."""

    # An important invariant maintained while a Task not done:
    # _fut_waiter is either None or a Future.  The Future
    # can be either done() or not done().
    # The task can be in any of 3 states:
    #
    # - 1: _fut_waiter is not None and not _fut_waiter.done():
    #      __step() is *not* scheduled and the Task is waiting for _fut_waiter.
    # - 2: (_fut_waiter is None or _fut_waiter.done()) and __step() is scheduled:
    #       the Task is waiting for __step() to be executed.
    # - 3:  _fut_waiter is None and __step() is *not* scheduled:
    #       the Task is currently executing (in __step()).
    #
    # * In state 1, one of the callbacks of __fut_waiter must be __wakeup().
    # * The transition from 1 to 2 happens when _fut_waiter becomes done(),
    #   as it schedules __wakeup() to be called (which calls __step() so
    #   we way that __step() is scheduled).
    # * It transitions from 2 to 3 when __step() is executed, and it clears
    #   _fut_waiter to None.

    def __init__(self, coro: Coroutine[None, None, T], *, loop: events.AbstractEventLoop | None = None,
                 name: str | None = None, eager_start: bool = False) -> None:
        super().__init__(loop=loop)
        # If False, don't log a message if the task is destroyed while its
        # status is still pending (Pystachy port: set here)
        self._log_destroy_pending = True

        if name is None:
            _task_name_counter[0] += 1
            self._name = f'Task-{_task_name_counter[0]}'
        else:
            self._name = str(name)

        self._num_cancels_requested = 0
        self._must_cancel = False
        self._fut_waiter: futures._FutureBase | None = None
        # Pystachy port: the coroutine that the task runs awaits coro, whose return value its
        # StopIteration does not carry here, and keeps that value (_run)
        self._user_coro = coro
        self._value: list[T] = []
        self._coro: Coroutine[None, None, None] = self._run(coro)

        if eager_start and self._loop.is_running():
            self.__eager_start()
        else:
            self._loop.call_soon(self.__step, None)
            _register_task(self)

    async def _run(self, coro: Coroutine[None, None, T]) -> None:
        self._value.append(await coro)

    def __repr__(self) -> str:
        # Pystachy port: base_tasks._task_repr_info(), without the coroutine's repr
        info = base_futures._future_repr_info(self)
        if self.cancelling() and not self.done():
            # replace status
            info[0] = 'cancelling'
        info.insert(1, 'name=%r' % self.get_name())
        if self._fut_waiter is not None:
            info.insert(2, f'wait_for={self._fut_waiter!r}')
        return '<{} {}>'.format(self.__class__.__name__, ' '.join(info))

    def get_coro(self) -> Coroutine[None, None, T]:
        return self._user_coro

    def get_name(self) -> str:
        return self._name

    def set_name(self, value: str) -> None:
        self._name = str(value)

    def set_result(self, result: T) -> None:
        raise RuntimeError('Task does not support set_result operation')

    def set_exception(self, exception: BaseException) -> None:
        raise RuntimeError('Task does not support set_exception operation')

    def cancel(self, msg: str | None = None) -> bool:
        """Request that this task cancel itself.

        This arranges for a CancelledError to be thrown into the
        wrapped coroutine on the next cycle through the event loop.
        The coroutine then has a chance to clean up or even deny
        the request using try/except/finally.

        Unlike Future.cancel, this does not guarantee that the
        task will be cancelled: the exception might be caught and
        acted upon, delaying cancellation of the task or preventing
        cancellation completely.  The task may also return a value or
        raise a different exception.

        Immediately after this method is called, Task.cancelled() will
        not return True (unless the task was already cancelled).  A
        task will be marked as cancelled when the wrapped coroutine
        terminates with a CancelledError exception (even if cancel()
        was not called).

        This also increases the task's count of cancellation requests.
        """
        if self.done():
            return False
        self._num_cancels_requested += 1
        # These two lines are controversial.  See discussion starting at
        # https://github.com/python/cpython/pull/31394#issuecomment-1053545331
        # Also remember that this is duplicated in _asynciomodule.c.
        # if self._num_cancels_requested > 1:
        #     return False
        waiter = self._fut_waiter
        if waiter is not None:
            if waiter.cancel(msg=msg):
                # Leave self._fut_waiter; it may be a Task that
                # catches and ignores the cancellation so we may have
                # to cancel it again later.
                return True
        # It must be the case that self.__step is already scheduled.
        self._must_cancel = True
        self._cancel_message = msg
        return True

    def cancelling(self) -> int:
        """Return the count of the task's cancellation requests.

        This count is incremented when .cancel() is called
        and may be decremented using .uncancel().
        """
        return self._num_cancels_requested

    def uncancel(self) -> int:
        """Decrement the task's count of cancellation requests.

        This should be called by the party that called `cancel()` on the task
        beforehand.

        Returns the remaining number of cancellation requests.
        """
        if self._num_cancels_requested > 0:
            self._num_cancels_requested -= 1
            if self._num_cancels_requested == 0:
                self._must_cancel = False
        return self._num_cancels_requested

    def __eager_start(self) -> None:
        prev_task = _swap_current_task(self._loop, self)
        try:
            _register_eager_task(self)
            try:
                self.__step_run_and_handle_result(None)
            finally:
                _unregister_eager_task(self)
        finally:
            curtask = _swap_current_task(self._loop, prev_task)
            assert curtask is self
            if not self.done():
                _register_task(self)

    def __step(self, exc: BaseException | None = None) -> None:
        if self.done():
            raise exceptions.InvalidStateError(
                f'_step(): already done: {self!r}, {exc!r}')
        if self._must_cancel:
            if not isinstance(exc, exceptions.CancelledError):
                exc = self._make_cancelled_error()
            self._must_cancel = False
        self._fut_waiter = None

        _enter_task(self._loop, self)
        try:
            self.__step_run_and_handle_result(exc)
        finally:
            _leave_task(self._loop, self)
            if self.done():
                _unregister_task(self)  # (Pystachy port: _scheduled_tasks holds what is not done)

    def __step_run_and_handle_result(self, exc: BaseException | None) -> None:
        coro = self._coro
        try:
            if exc is None:
                # We use the `send` method directly, because coroutines
                # don't have `__iter__` and `__next__` methods.
                coro.send(None)
            else:
                coro.throw(exc)
        except StopIteration:
            if self._must_cancel:
                # Task is cancelled right before coro stops.
                self._must_cancel = False
                super().cancel(msg=self._cancel_message)
            else:
                super().set_result(self._value[0])
        except (KeyboardInterrupt, SystemExit) as exc:
            super().set_exception(exc)
            raise
        except BaseException as exc:
            if isinstance(exc, exceptions.CancelledError):
                # Save the original exception so we can chain it later.
                self._cancelled_exc = exc
                super().cancel()  # I.e., Future.cancel(self).
            else:
                super().set_exception(exc)
        else:
            # Pystachy port: what the coroutine awaits, which an await of a future recorded
            # (futures._waiting_on), where CPython's yields it; else a bare yield
            result = futures._waiting_on.pop() if len(futures._waiting_on) > 0 else None
            if result is not None:
                blocking = result._asyncio_future_blocking
                # Yielded Future must come from Future.__iter__().
                if futures._get_loop(result) is not self._loop:
                    new_exc = RuntimeError(
                        f'Task {self!r} got Future '
                        f'{result!r} attached to a different loop')
                    self._loop.call_soon(
                        self.__step, exceptions._as_exception(new_exc))
                elif blocking:
                    if result is self:
                        new_exc = RuntimeError(
                            f'Task cannot await on itself: {self!r}')
                        self._loop.call_soon(
                            self.__step, exceptions._as_exception(new_exc))
                    else:
                        result._asyncio_future_blocking = False
                        self.__wait_on(result)
                        self._fut_waiter = result
                        if self._must_cancel:
                            if result.cancel(
                                    msg=self._cancel_message):
                                self._must_cancel = False
            else:
                # Bare yield relinquishes control for one event loop iteration.
                self._loop.call_soon(self.__step, None)

    def __wait_on(self, result: futures._FutureBase) -> None:
        # Pystachy port: result.add_done_callback(self.__wakeup)
        def wakeup() -> None:
            self.__wakeup(result)

        result._add_callback(wakeup)

    def __wakeup(self, future: futures._FutureBase) -> None:
        try:
            future._check_result()
        except BaseException as exc:
            # This may also be a cancellation.
            self.__step(exc)
        else:
            # Don't pass the value of `future.result()` explicitly,
            # as `Future.__iter__` and `Future.__await__` don't need it.
            # If we call `_step(value, None)` instead of `_step()`,
            # Python eval loop would use `.send(value)` method call,
            # instead of `__next__()`, which is slower for futures
            # that return non-generator iterators from their `__iter__`.
            self.__step()


_PyTask = Task


def create_task(coro, *, name: str | None = None, context=None):
    """Schedule the execution of a coroutine object in a spawn task.

    Return a Task object.
    """
    loop = events.get_running_loop()
    return _create_task(loop, coro, name)


def _create_task(loop: events.AbstractEventLoop, coro, name: str | None):
    # Pystachy port: loop.create_task(), which makes a Task of coro's result type, as a function
    # (BaseEventLoop.create_task calls it); the loop's eager flag is its task factory
    if loop.is_closed():
        raise RuntimeError('Event loop is closed')
    return Task(coro, loop=loop, name=name, eager_start=loop._eager_tasks())


@types.coroutine
def __sleep0():
    """Skip one event loop run cycle.

    This is a private helper for 'asyncio.sleep()', used
    when the 'delay' is set to 0.  It uses a bare 'yield'
    expression (which Task.__step knows how to handle)
    instead of creating a Future object.
    """
    yield None


async def sleep(delay, result=None):
    """Coroutine that completes after a given time (in seconds)."""
    if delay <= 0:
        await __sleep0()
        return result

    if math.isnan(delay):
        raise ValueError("Invalid delay: NaN (not a number)")

    loop = events.get_running_loop()
    # Pystachy port: a Future[None], whose result the coroutine returns as result
    future: futures.Future[None] = futures.Future(loop=loop)
    h = loop.call_later(float(delay),  # (Pystachy port: an int converted)
                        futures._set_result_unless_cancelled,
                        future, None)
    try:
        await future
        return result
    finally:
        h.cancel()


def ensure_future(coro_or_future, *, loop: events.AbstractEventLoop | None = None):
    """Wrap a coroutine or an awaitable in a future.

    If the argument is a Future, it is returned directly.
    """
    # Pystachy port: a Future (or Task) or a coroutine, by its type (isinstance() decides it as
    # the function compiles)
    if isinstance(coro_or_future, futures._FutureBase):
        if loop is not None and loop is not futures._get_loop(coro_or_future):
            raise ValueError('The future belongs to a different loop than '
                            'the one specified as the loop argument')
        return coro_or_future
    if isinstance(coro_or_future, types.CoroutineType):
        if loop is None:
            loop = events.get_event_loop()
        return _create_task(loop, coro_or_future, None)
    raise TypeError('An asyncio.Future, a coroutine or an awaitable '
                    'is required')


class _GatheringFuture(futures.Future[T]):
    """Helper for gather().

    This overrides cancel() to cancel all the children and act more
    like Task.cancel(), which doesn't immediately mark itself as
    cancelled.
    """

    # Pystachy port: results is the empty list of the children's results whose type binds T
    def __init__(self, children: list[futures._FutureBase], results: T, *,
                 loop: events.AbstractEventLoop) -> None:
        super().__init__(loop=loop)
        self._children = children
        self._cancel_requested = False

    def cancel(self, msg: str | None = None) -> bool:
        if self.done():
            return False
        ret = False
        for child in self._children:
            if child.cancel(msg=msg):
                ret = True
        if ret:
            # If any child tasks were actually cancelled, we should
            # propagate the cancellation request regardless of
            # *return_exceptions* argument.  See issue 32684.
            self._cancel_requested = True
        return ret


def gather(*coros_or_futures, return_exceptions: bool = False):
    """Return a future aggregating results from the given coroutines/futures.

    Coroutines will be wrapped in a future and scheduled in the event
    loop. They will not necessarily be scheduled in the same order as
    passed in.

    All futures must share the same event loop.  If all the tasks are
    done successfully, the returned future's result is the list of
    results (in the order of the original sequence, not necessarily
    the order of results arrival).  If *return_exceptions* is True,
    exceptions in the tasks are treated the same as successful
    results, and gathered in the result list; otherwise, the first
    raised exception will be immediately propagated to the returned
    future.

    Cancellation: if the outer Future is cancelled, all children (that
    have not completed yet) are also cancelled.  If any child is
    cancelled, this is treated as if it raised CancelledError --
    the outer Future is *not* cancelled in this case.  (This is to
    prevent the cancellation of one child to cause other children to
    be cancelled.)

    If *return_exceptions* is False, cancelling gather() after it
    has been marked done won't cancel any submitted awaitables.
    For instance, gather can be marked done after propagating an
    exception to the caller, therefore, calling ``gather.cancel()``
    after catching an exception (raised by one of the awaitables) from
    gather won't cancel any other awaitables.
    """
    # Pystachy port: the awaitables are coroutines or futures of one result type, of which the
    # result is a list; return_exceptions=True is not supported (a list of results and
    # exceptions), and an awaitable given twice is run twice (not deduplicated)
    if return_exceptions:
        raise NotImplementedError("gather(return_exceptions=True) is not supported")
    loop: events.AbstractEventLoop | None = None
    children = [ensure_future(arg, loop=loop) for arg in coros_or_futures[:1]]
    loop = futures._get_loop(children[0])
    for arg in coros_or_futures[1:]:
        children.append(ensure_future(arg, loop=loop))
    bases: list[futures._FutureBase] = []
    for fut in children:
        bases.append(fut)
    results = [fut.result() for fut in children if fut is None]
    outer = _GatheringFuture(bases, results, loop=loop)
    nfuts = len(children)
    nfinished = [0]

    def _done_callback(fut) -> None:
        nfinished[0] += 1

        if outer.done():
            if not fut.cancelled():
                # Mark exception retrieved.
                fut.exception()
            return

        if fut.cancelled():
            # Check if 'fut' is cancelled first, as
            # 'fut.exception()' will *raise* a CancelledError
            # instead of returning it.
            exc = fut._make_cancelled_error()
            outer.set_exception(exc)
            return
        else:
            exc = fut.exception()
            if exc is not None:
                outer.set_exception(exc)
                return

        if nfinished[0] == nfuts:
            # All futures are done; create a list of results
            # and set it to the 'outer' future.
            for fut in children:
                results.append(fut.result())

            if outer._cancel_requested:
                # If gather is being cancelled we must propagate the
                # cancellation regardless of *return_exceptions* argument.
                # See issue 32684.
                exc = fut._make_cancelled_error()
                outer.set_exception(exc)
            else:
                outer.set_result(results)

    done_futs = []
    for fut in children:
        if fut.done():
            done_futs.append(fut)
        else:
            fut.add_done_callback(_done_callback)

    for fut in done_futs:
        _done_callback(fut)
    return outer


async def wait_for(fut, timeout):
    """Wait for the single Future or coroutine to complete, with timeout.

    Coroutine will be wrapped in Task.

    Returns result of the Future or coroutine.  When a timeout occurs,
    it cancels the task and raises TimeoutError.  To avoid the task
    cancellation, wrap it in shield().

    If the wait is cancelled, the task is also cancelled.

    If the task suppresses the cancellation and returns a value instead,
    that value is returned.

    This function is a coroutine.
    """
    # The special case for timeout <= 0 is for the following case:
    #
    # async def test_waitfor():
    #     func_started = False
    #
    #     async def func():
    #         nonlocal func_started
    #         func_started = True
    #
    #     try:
    #         await asyncio.wait_for(func(), 0)
    #     except asyncio.TimeoutError:
    #         assert not func_started
    #     else:
    #         assert False
    #
    # Pystachy port: a coroutine or future; a timeout of None waits for it
    async with timeouts.timeout(timeout):
        return await ensure_future(fut)


def create_eager_task_factory(custom_task_constructor):
    """Create a function suitable for use as a task factory on an event-loop.

    Pystachy port: only Task's eager factory, eager_task_factory, is supported
    """
    raise NotImplementedError("create_eager_task_factory() is not supported: use eager_task_factory")


def eager_task_factory(loop, coro, *, name=None, context=None):
    # Pystachy port: a loop whose task factory this is makes eager tasks (loop.set_task_factory)
    return Task(coro, loop=loop, name=name, eager_start=True)


# Collectively these two sets hold references to the complete set of active
# tasks. Eagerly executed tasks use a faster regular set as an optimization
# but may graduate to a WeakSet if the task blocks on IO.
# Pystachy port: dicts whose keys are the tasks that are not done
_scheduled_tasks: dict[futures._FutureBase, bool] = {}
_eager_tasks: dict[futures._FutureBase, bool] = {}

# Dictionary containing tasks that are currently active in
# all running event loops.  {EventLoop: Task}
_current_tasks: dict[events.AbstractEventLoop, futures._FutureBase] = {}


def _register_task(task: futures._FutureBase) -> None:
    """Register an asyncio Task scheduled to run on an event loop."""
    _scheduled_tasks[task] = True


def _register_eager_task(task: futures._FutureBase) -> None:
    """Register an asyncio Task about to be eagerly executed."""
    _eager_tasks[task] = True


def _enter_task(loop: events.AbstractEventLoop, task: futures._FutureBase) -> None:
    current_task = _current_tasks.get(loop, None)
    if current_task is not None:
        raise RuntimeError(f"Cannot enter into task {task!r} while another "
                           f"task {current_task!r} is being executed.")
    _current_tasks[loop] = task


def _leave_task(loop: events.AbstractEventLoop, task: futures._FutureBase) -> None:
    current_task = _current_tasks.get(loop, None)
    if current_task is not task:
        raise RuntimeError(f"Leaving task {task!r} does not match "
                           f"the current task {current_task!r}.")
    del _current_tasks[loop]


def _swap_current_task(loop: events.AbstractEventLoop, task: futures._FutureBase | None) -> futures._FutureBase | None:
    prev_task = _current_tasks.get(loop, None)
    if task is None:
        if loop in _current_tasks:
            del _current_tasks[loop]
    else:
        _current_tasks[loop] = task
    return prev_task


def _unregister_task(task: futures._FutureBase) -> None:
    """Unregister a completed, scheduled Task."""
    _scheduled_tasks.pop(task, False)


def _unregister_eager_task(task: futures._FutureBase) -> None:
    """Unregister a task which finished its first eager step."""
    _eager_tasks.pop(task, False)
