"""This module provides primitive operations to write multi-threaded programs.
The 'threading' module provides a more convenient interface."""
# _thread for Pystachy: CPython builds _thread into its interpreter (Modules/_threadmodule.c), so
# Pystachy loads this port of it for import _thread (specs.STANDINS). A Pystachy program runs one
# thread, as CPython's builds without threads did (_dummy_thread, until 3.8): starting another
# raises NotImplementedError, and a lock is a flag. Acquiring a locked lock does what CPython's
# does where no other thread releases it: it gives False at once without blocking, or after its
# timeout, which it sleeps; where it would wait for ever, it raises RuntimeError instead (a
# deadlock). The arguments' checks and the messages are the C module's. The docstrings are
# CPython 3.13.16's.
from builtins import RuntimeError as error
import math
import os
import time

__all__ = ["LockType", "RLock", "TIMEOUT_MAX", "allocate", "allocate_lock", "daemon_threads_allowed", "error", "exit",
           "exit_thread", "get_ident", "get_native_id", "interrupt_main", "lock", "stack_size", "start_joinable_thread",
           "start_new", "start_new_thread"]

TIMEOUT_MAX = 9223372036.0  # (PY_TIMEOUT_MAX's seconds, floored, on 64-bit Linux)
_NS_MAX = 9223372036854775807  # (PyTime_MAX, nanoseconds)
_DEADLOCK = "deadlock: acquire() would wait for ever, as Pystachy runs no other thread to release the lock"
_stacksize = 0


def _wait(blocking, timeout) -> float:
    # the seconds acquire() of a locked lock waits, -1.0 for ever (lock_acquire_parse_args), where
    # its arguments are valid: a timeout of seconds, -1 for none, converted to nanoseconds as
    # Python/pytime.c's pytime_from_object() converts it, rounded away from zero
    if isinstance(timeout, float):
        if timeout != timeout:
            raise ValueError("Invalid value NaN (not a number)")
        d = timeout * 1e9
        if not (-9223372036854775808.0 <= d < 9223372036854775808.0):
            raise OverflowError("timestamp out of range for C PyTime_t")  # (rounding moves no float this large)
        ns = math.ceil(d) if d >= 0.0 else math.floor(d)
        unset = ns == -1000000000
        negative = ns < 0
        seconds = ns / 1e9
    else:
        t = int(timeout)
        if t > _NS_MAX // 1000000000 or t < -(_NS_MAX // 1000000000):
            raise OverflowError("timestamp out of range for C PyTime_t")
        unset = t == -1
        negative = t < 0
        seconds = float(t)
    if not blocking and not unset:
        raise ValueError("can't specify a timeout for a non-blocking call")
    if negative and not unset:
        raise ValueError("timeout value must be a non-negative number")
    if not blocking:
        return 0.0
    return -1.0 if unset else seconds


def _blocked(wait: float) -> bool:
    # acquire() of a lock that stays locked: False, after the timeout where it has one
    if wait < 0.0:
        raise RuntimeError(_DEADLOCK)
    if wait > 0.0:
        time.sleep(wait)
    return False


class _Place:
    # (an object whose default repr gives an address, for the reprs of the locks below)
    pass


def _at(p: _Place) -> str:
    r = repr(p)
    return r[r.rfind(" at ") :]


class lock:
    """A lock object is a synchronization primitive.  To create a lock,
call threading.Lock().  Methods are:

acquire() -- lock the lock, possibly blocking until it can be obtained
release() -- unlock of the lock
locked() -- test whether the lock is currently locked

A lock is not owned by the thread that locked it; another thread may
unlock it.  A thread attempting to lock a lock that it has already locked
will block until another thread unlocks it.  Deadlocks may ensue."""

    def __init__(self) -> None:
        self._locked = False
        self._place = _Place()

    def acquire(self, blocking=True, timeout=-1) -> bool:
        """Lock the lock.  Without argument, this blocks if the lock is already
locked (even by the same thread), waiting for another thread to release
the lock, and return True once the lock is acquired.
With an argument, this will only block if the argument is true,
and the return value reflects whether the lock is acquired.
The blocking operation is interruptible."""
        wait = _wait(blocking, timeout)
        if self._locked:
            return _blocked(wait)
        self._locked = True
        return True

    def acquire_lock(self, blocking=True, timeout=-1) -> bool:
        """An obsolete synonym of acquire()."""
        return self.acquire(blocking, timeout)

    def release(self) -> None:
        """Release the lock, allowing another thread that is blocked waiting for
the lock to acquire the lock.  The lock must be in the locked state,
but it needn't be locked by the same thread that unlocks it."""
        if not self._locked:
            raise RuntimeError("release unlocked lock")
        self._locked = False

    def release_lock(self) -> None:
        """An obsolete synonym of release()."""
        self.release()

    def __enter__(self):  # (compiled only where a with statement calls it, as __exit__ is)
        """Lock the lock (with lock: ...), as acquire() does."""
        return self.acquire()

    def __exit__(self, *args) -> None:
        """Release the lock, as release() does."""
        self.release()

    def locked(self) -> bool:
        """Return whether the lock is in the locked state."""
        return self._locked

    def locked_lock(self) -> bool:
        """An obsolete synonym of locked()."""
        return self._locked

    def _at_fork_reinit(self) -> None:
        self._locked = False

    def __repr__(self) -> str:
        return f"<{'locked' if self._locked else 'unlocked'} _thread.lock object{_at(self._place)}"


LockType = lock


class RLock:
    def __init__(self) -> None:
        self._owner = 0
        self._count = 0
        self._place = _Place()

    def acquire(self, blocking=True, timeout=-1) -> bool:
        """Lock the lock.  `blocking` indicates whether we should wait
for the lock to be available or not.  If `blocking` is False
and another thread holds the lock, the method will return False
immediately.  If `blocking` is True and another thread holds
the lock, the method will wait for the lock to be released,
take it and then return True.
(note: the blocking operation is interruptible.)

In all other cases, the method will return True immediately.
Precisely, if the current thread already holds the lock, its
internal counter is simply incremented. If nobody holds the lock,
the lock is taken and its internal counter initialized to 1."""
        wait = _wait(blocking, timeout)
        if self._count > 0 and self._owner == get_ident():
            self._count += 1
            return True
        if self._count > 0:
            return _blocked(wait)  # (held for an owner that _acquire_restore() gave it)
        self._owner = get_ident()
        self._count = 1
        return True

    def release(self) -> None:
        """Release the lock, allowing another thread that is blocked waiting for
the lock to acquire the lock.  The lock must be in the locked state,
and must be locked by the same thread that unlocks it; otherwise a
`RuntimeError` is raised.

Do note that if the lock was acquire()d several times in a row by the
current thread, release() needs to be called as many times for the lock
to be available for other threads."""
        if self._count == 0 or self._owner != get_ident():
            raise RuntimeError("cannot release un-acquired lock")
        self._count -= 1
        if self._count == 0:
            self._owner = 0

    def __enter__(self):  # (compiled only where a with statement calls it, as __exit__ is)
        """Lock the lock (with lock: ...), as acquire() does."""
        return self.acquire()

    def __exit__(self, *args) -> None:
        """Release the lock, as release() does."""
        self.release()

    def _is_owned(self) -> bool:
        """For internal use by `threading.Condition`."""
        return self._count > 0 and self._owner == get_ident()

    def _recursion_count(self) -> int:
        """For internal use by reentrancy checks."""
        return self._count if self._owner == get_ident() else 0

    def _release_save(self) -> tuple[int, int]:
        """For internal use by `threading.Condition`."""
        if self._count == 0:
            raise RuntimeError("cannot release un-acquired lock")
        state = (self._count, self._owner)
        self._count = 0
        self._owner = 0
        return state

    def _acquire_restore(self, state: tuple[int, int], /) -> None:
        """For internal use by `threading.Condition`."""
        if self._count > 0:
            raise RuntimeError(_DEADLOCK)
        self._count = state[0]
        self._owner = state[1]

    def _at_fork_reinit(self) -> None:
        self._owner = 0
        self._count = 0

    def __repr__(self) -> str:
        return f"<{'locked' if self._count > 0 else 'unlocked'} _thread.RLock object owner={self._owner} count={self._count}{_at(self._place)}"


class _local:
    """Thread-local data"""
    # (one thread's: a subclass's __init__ binds its fields, as for any class)


class _ThreadHandle:
    def __init__(self, ident: int) -> None:
        self._ident = ident
        self._done = False

    @property
    def ident(self) -> int:
        return self._ident

    def join(self, timeout: float | None = None) -> None:
        # (ThreadHandle_join: of the running thread, an error; of a thread not done, a wait that
        # no thread ends)
        if self._done:
            return
        if self._ident == get_ident():
            raise RuntimeError("Cannot join current thread")
        if timeout is None or timeout < 0:
            raise RuntimeError("deadlock: join() would wait for ever, as Pystachy runs no other thread")
        time.sleep(timeout)

    def is_done(self) -> bool:
        return self._done

    def _set_done(self) -> None:
        self._done = True

    def __repr__(self) -> str:
        return f"<_thread._ThreadHandle object: ident={self._ident}>"


class _ExceptHookArgs:
    """ExceptHookArgs

Type used to pass arguments to threading.excepthook."""
    # (CPython's struct sequence of four: what threading gives excepthook where a thread's run()
    # raises, which no thread but the main one does here)

    def __init__(self, args) -> None:
        self.exc_type = args[0]
        self.exc_value = args[1]
        self.exc_traceback = args[2]
        self.thread = args[3]


def _excepthook(args, /) -> None:
    """Handle uncaught Thread.run() exception."""
    raise NotImplementedError("_thread._excepthook() is not supported: a Pystachy program runs no thread whose exception it would report")


def allocate_lock() -> lock:
    """Create a new lock object. See help(type(threading.Lock())) for
information about locks."""
    return lock()


def allocate() -> lock:
    """An obsolete synonym of allocate_lock()."""
    return lock()


def get_ident() -> int:
    """Return a non-zero integer that uniquely identifies the current thread
amongst other threads that exist simultaneously.
This may be used to identify per-thread resources.
Even though on some platforms threads identities may appear to be
allocated consecutive numbers starting at 1, this behavior should not
be relied upon, and the number should be seen purely as a magic cookie.
A thread's identity may be reused for another thread after it exits."""
    return os.getpid()  # (the only thread's: a non-zero integer, as pthread_self()'s is)


def get_native_id() -> int:
    """Return a non-negative integer identifying the thread as reported
by the OS (kernel). This may be used to uniquely identify a
particular thread within a system."""
    return os.getpid()  # (Linux gives a process's main thread the process's id)


def _get_main_thread_ident() -> int:
    """Internal only. Return a non-zero integer that uniquely identifies the main thread
of the main interpreter."""
    return get_ident()


def _count() -> int:
    """Return the number of currently running Python threads, excluding
the main thread. The returned number comprises all threads created
through `start_new_thread()` as well as `threading.Thread`, and not
yet finished.

This function is meant for internal and specialized purposes only.
In most applications `threading.enumerate()` should be used instead."""
    return 0


def _make_thread_handle(ident: int, /) -> _ThreadHandle:
    """Internal only. Make a thread handle for threads not spawned
by the _thread or threading module."""
    return _ThreadHandle(ident)


def _is_main_interpreter() -> bool:
    """Return True if the current interpreter is the main Python interpreter."""
    return True


def daemon_threads_allowed() -> bool:
    """Return True if daemon threads are allowed in the current interpreter,
and False otherwise.
"""
    return True


def _shutdown() -> None:
    """Wait for all non-daemon threads (other than the calling thread) to stop."""


def start_new_thread(function, args, kwargs=None, /) -> int:
    """Start a new thread and return its identifier.

The thread will call the function with positional arguments from the
tuple args and keyword arguments taken from the optional dictionary
kwargs.  The thread exits when the function returns; the return value
is ignored.  The thread will also exit when the function raises an
unhandled exception; a stack trace will be printed unless the exception
is SystemExit."""
    raise NotImplementedError("_thread.start_new_thread() is not supported: a Pystachy program runs one thread")


def start_new(function, args, kwargs=None, /) -> int:
    """An obsolete synonym of start_new_thread()."""
    raise NotImplementedError("_thread.start_new() is not supported: a Pystachy program runs one thread")


def start_joinable_thread(function, handle=None, daemon=True) -> _ThreadHandle:
    """*For internal use only*: start a new thread.

Like start_new_thread(), this starts a new thread calling the given function.
Unlike start_new_thread(), this returns a handle object with methods to join
or detach the given thread.
This function is not for third-party code, please use the
`threading` module instead. During finalization the runtime will not wait for
the thread to exit if daemon is True. If handle is provided it must be a
newly created thread._ThreadHandle instance."""
    raise NotImplementedError("_thread.start_joinable_thread() is not supported: a Pystachy program runs one thread")


def stack_size(size: int = 0, /) -> int:
    """Return the thread stack size used when creating new threads.  The
optional size argument specifies the stack size (in bytes) to be used
for subsequently created threads, and must be 0 (use platform or
configured default) or a positive integer value of at least 32,768 (32k).
If changing the thread stack size is unsupported, a ThreadError
exception is raised.  If the specified size is invalid, a ValueError
exception is raised, and the stack size is unmodified.  32k bytes
 currently the minimum supported stack size value to guarantee
sufficient stack space for the interpreter itself.

Note that some platforms may have particular restrictions on values for
the stack size, such as requiring a minimum stack size larger than 32 KiB or
requiring allocation in multiples of the system memory page size
- platform documentation should be referred to for more information
(4 KiB pages are common; using multiples of 4096 for the stack size is
the suggested approach in the absence of more specific information)."""
    global _stacksize
    if size < 0:
        raise ValueError("size must be 0 or a positive value")
    if not __pys_thread_stack_valid(size):
        raise ValueError(f"size not valid: {size} bytes")
    old = _stacksize
    _stacksize = size
    return old


def interrupt_main(signum: int = 2, /) -> None:
    """Simulate the arrival of the given signal in the main thread,
where the corresponding signal handler will be executed.
If *signum* is omitted, SIGINT is assumed.
A subthread can use this function to interrupt the main thread.

Note: the default signal handler for SIGINT raises ``KeyboardInterrupt``."""
    # (the handlers CPython has as it starts: SIGINT's raises KeyboardInterrupt, the others' do
    # nothing, as SIG_DFL and SIG_IGN are not run)
    if signum < 1 or signum >= 65:
        raise ValueError("signal number out of range")
    if signum == 2:
        raise KeyboardInterrupt


def exit() -> None:
    """This is synonymous to ``raise SystemExit''.  It will cause the current
thread to exit silently unless the exception is caught."""
    raise SystemExit


def exit_thread() -> None:
    """An obsolete synonym of exit()."""
    raise SystemExit
