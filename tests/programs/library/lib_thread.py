# _thread (lib/_pystachy_thread.py, the stand-in Pystachy loads for the C module): locks and
# reentrant locks in the one thread a program runs, acquire()'s checks of its arguments with
# CPython's messages, thread identities and handles, stack_size(), interrupt_main(), exit(), and
# _local as a base class
import _thread
from _thread import RLock, allocate_lock, get_ident


def acquire(blocking: bool, timeout: float) -> None:
    # (a fresh lock: an unlocked one is acquired at once where the arguments are valid)
    try:
        print(blocking, timeout, allocate_lock().acquire(blocking, timeout))
    except (ValueError, OverflowError) as e:
        print(blocking, timeout, type(e).__name__, e)


def acquire_int(blocking: bool, timeout: int) -> None:
    try:
        print(blocking, timeout, allocate_lock().acquire(blocking, timeout))
    except (ValueError, OverflowError) as e:
        print(blocking, timeout, type(e).__name__, e)


lock = allocate_lock()
print(repr(lock).startswith("<unlocked _thread.lock object at 0x"), lock.locked())
print(lock.acquire(), lock.locked(), repr(lock).startswith("<locked _thread.lock object at 0x"))
print(lock.acquire(False), lock.acquire(True, 0.01), lock.acquire(timeout=0), lock.acquire(blocking=False))
print(lock.acquire_lock(False), lock.locked_lock())
lock.release()
print(lock.locked())
try:
    lock.release()
except _thread.error as e:
    print("error:", e)
try:
    lock.release_lock()
except RuntimeError as e:
    print("RuntimeError:", e)
for t in [-1.0, 0.0, 1.5, -2.0, -0.5, -1e-12, 9223372036.0, 9223372036.854776, 1e20, float("inf"), float("-inf"), float("nan")]:
    acquire(True, t)
for n in [0, 1, -1, -3, 9223372036, 9223372037, -9223372037]:
    acquire_int(True, n)
acquire(False, 0.0)
acquire(False, -1.0)
acquire_int(False, 0)
acquire_int(False, -1)
print(allocate_lock().acquire(0), allocate_lock().acquire(""), allocate_lock().acquire([1]))

r = RLock()
print(repr(r).split(" at 0x")[0], r._is_owned(), r._recursion_count())
print(r.acquire(), r.acquire(False), r.acquire(True, 5.0), r._is_owned(), r._recursion_count())
print(repr(r).split(" at 0x")[0].replace(str(get_ident()), "ID"))
state = r._release_save()
print(state[0], state[1] == get_ident(), r._is_owned(), r._recursion_count(), repr(r).split(" at 0x")[0])
r._acquire_restore(state)
print(r._recursion_count(), r._is_owned())
r.release()
r.release()
r.release()
print(r._is_owned())
for k in range(2):
    try:
        if k == 0:
            r.release()
        else:
            r._release_save()
    except RuntimeError as e:
        print("RuntimeError:", e)

print(get_ident() == get_ident(), get_ident() != 0, _thread._get_main_thread_ident() == get_ident(), _thread.get_native_id() > 0)
print(_thread._count(), _thread.daemon_threads_allowed(), _thread._is_main_interpreter(), _thread.TIMEOUT_MAX)
print(repr(_thread.allocate()).split(" object")[0], repr(RLock()).split(" object")[0])
handle = _thread._make_thread_handle(get_ident())
print(repr(handle).replace(str(get_ident()), "ID"), handle.is_done(), handle.ident == get_ident())
try:
    handle.join()
except RuntimeError as e:
    print("RuntimeError:", e)
handle._set_done()
handle.join()
print(handle.is_done())
_thread._shutdown()

for size in [32768, 1 << 40, 32767, -1, 0]:
    try:
        print(size, _thread.stack_size(size), _thread.stack_size())
    except ValueError as e:
        print(size, "ValueError:", e)
for signum in [15, 1, 64, 0, 65, -1]:
    try:
        print(signum, _thread.interrupt_main(signum))
    except ValueError as e:
        print(signum, "ValueError:", e)
try:
    _thread.interrupt_main()
    print("not interrupted")
except KeyboardInterrupt as e:
    print("KeyboardInterrupt", repr(e))
for k in range(2):
    try:
        if k == 0:
            _thread.exit()
        else:
            _thread.exit_thread()
    except SystemExit as e:
        print("SystemExit", repr(e))


class Local(_thread._local):
    def __init__(self, x: int) -> None:
        self.x = x


data = Local(3)
data.x += 1
print(data.x)
print(_thread.__doc__)
