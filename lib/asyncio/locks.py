"""Synchronization primitives."""

# Pystachy port: Lock and Event; no Condition, Semaphore, BoundedSemaphore or Barrier
# (lib/compatibility.md#asyncio)
__all__ = ('Lock', 'Event')

from types import TracebackType

from . import events
from . import exceptions
from . import futures


class _ContextManagerMixin:
    async def __aenter__(self) -> None:
        await self.acquire()
        # We have no use for the "as ..."  clause in the with
        # statement for locks.
        return None

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.release()

    async def acquire(self) -> bool:
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError


class _LoopBound:
    # Pystachy port: mixins._LoopBoundMixin's loop, held by each class (a mixin holds no fields)
    def __init__(self) -> None:
        self._loop: events.AbstractEventLoop | None = None

    def _get_loop(self) -> events.AbstractEventLoop:
        loop = events.get_running_loop()

        if self._loop is None:
            self._loop = loop
        if loop is not self._loop:
            raise RuntimeError(f'{self!r} is bound to a different event loop')
        return loop


class Lock(_ContextManagerMixin):
    """Primitive lock objects.

    A primitive lock is a synchronization primitive that is not owned
    by a particular task when locked.  A primitive lock is in one
    of two states, 'locked' or 'unlocked'.

    It is created in the unlocked state.  It has two basic methods,
    acquire() and release().  When the state is unlocked, acquire()
    changes the state to locked and returns immediately.  When the
    state is locked, acquire() blocks until a call to release() in
    another task changes it to unlocked, then the acquire() call
    resets it to locked and returns.  The release() method should only
    be called in the locked state; it changes the state to unlocked
    and returns immediately.  If an attempt is made to release an
    unlocked lock, a RuntimeError will be raised.

    When more than one task is blocked in acquire() waiting for
    the state to turn to unlocked, only one task proceeds when a
    release() call resets the state to unlocked; successive release()
    calls will unblock tasks in FIFO order.

    Locks also support the asynchronous context management protocol.
    'async with lock' statement should be used.

    Usage:

        lock = Lock()
        ...
        await lock.acquire()
        try:
            ...
        finally:
            lock.release()

    Context manager usage:

        lock = Lock()
        ...
        async with lock:
             ...

    Lock objects can be tested for locking state:

        if not lock.locked():
           await lock.acquire()
        else:
           # lock is acquired
           ...

    """

    def __init__(self) -> None:
        self._bound = _LoopBound()
        # Pystachy port: a list for the deque, which is made empty
        self._waiters: list[futures.Future[bool]] = []
        self._locked = False

    def __repr__(self) -> str:
        res = super().__repr__()
        extra = 'locked' if self._locked else 'unlocked'
        if self._waiters:
            extra = f'{extra}, waiters:{len(self._waiters)}'
        return f'<{res[1:-1]} [{extra}]>'

    def locked(self) -> bool:
        """Return True if lock is acquired."""
        return self._locked

    async def acquire(self) -> bool:
        """Acquire a lock.

        This method blocks until the lock is unlocked, then sets it to
        locked and returns True.
        """
        # Implement fair scheduling, where thread always waits
        # its turn. Jumping the queue if all are cancelled is an optimization.
        if (not self._locked and (not self._waiters or
                all(w.cancelled() for w in self._waiters))):
            self._locked = True
            return True

        fut: futures.Future[bool] = futures.Future(loop=self._bound._get_loop())
        self._waiters.append(fut)

        try:
            try:
                await fut
            finally:
                self._waiters.remove(fut)
        except exceptions.CancelledError:
            # Currently the only exception designed be able to occur here.

            # Ensure the lock invariant: If lock is not claimed (or about
            # to be claimed by us) and there is a Task in waiters,
            # ensure that the Task at the head will run.
            if not self._locked:
                self._wake_up_first()
            raise

        # assert self._locked is False
        self._locked = True
        return True

    def release(self) -> None:
        """Release a lock.

        When the lock is locked, reset it to unlocked, and return.
        If any other tasks are blocked waiting for the lock to become
        unlocked, allow exactly one of them to proceed.

        When invoked on an unlocked lock, a RuntimeError is raised.

        There is no return value.
        """
        if self._locked:
            self._locked = False
            self._wake_up_first()
        else:
            raise RuntimeError('Lock is not acquired.')

    def _wake_up_first(self) -> None:
        """Ensure that the first waiter will wake up."""
        if not self._waiters:
            return
        fut = self._waiters[0]

        # .done() means that the waiter is already set to wake up.
        if not fut.done():
            fut.set_result(True)


class Event:
    """Asynchronous equivalent to threading.Event.

    Class implementing event objects.  An event manages a flag that can be
    set to true with the set() method and reset to false with the clear()
    method.  The wait() method blocks until the flag is true.  The flag is
    initially false.
    """

    def __init__(self) -> None:
        self._bound = _LoopBound()
        self._waiters: list[futures.Future[bool]] = []
        self._value = False

    def __repr__(self) -> str:
        res = super().__repr__()
        extra = 'set' if self._value else 'unset'
        if self._waiters:
            extra = f'{extra}, waiters:{len(self._waiters)}'
        return f'<{res[1:-1]} [{extra}]>'

    def is_set(self) -> bool:
        """Return True if and only if the internal flag is true."""
        return self._value

    def set(self) -> None:
        """Set the internal flag to true. All tasks waiting for it to
        become true are awakened. Tasks that call wait() once the flag is
        true will not block at all.
        """
        if not self._value:
            self._value = True

            for fut in self._waiters:
                if not fut.done():
                    fut.set_result(True)

    def clear(self) -> None:
        """Reset the internal flag to false. Subsequently, tasks calling
        wait() will block until set() is called to set the internal flag
        to true again."""
        self._value = False

    async def wait(self) -> bool:
        """Block until the internal flag is true.

        If the internal flag is true on entry, return True
        immediately.  Otherwise, block until another task calls
        set() to set the flag to true, then return True.
        """
        if self._value:
            return True

        fut: futures.Future[bool] = futures.Future(loop=self._bound._get_loop())
        self._waiters.append(fut)
        try:
            await fut
            return True
        finally:
            self._waiters.remove(fut)
