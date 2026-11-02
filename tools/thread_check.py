"""Check lib/_pystachy_thread.py on CPython against CPython's C module _thread.

The port's locks run in one thread, so this compares what one thread can see: acquire() of an
unlocked lock and of a reentrant one, for random arguments (blocking flags, timeouts of int and
float at the edges of PyTime_t's range, NaN and infinities), with the values and errors of
_thread's; release() of an unlocked lock; the RLock's counts and its state through _release_save()
and _acquire_restore(); stack_size(), interrupt_main() and the constants. The port's functions and
methods must have the C module's signatures, docstrings and names.
Usage: python3 -I tools/thread_check.py [--rounds N]
"""
import _thread
import argparse
import importlib.util
import inspect
import math
from pathlib import Path
import random
import sys

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def outcome(f, *args):
    try:
        r = f(*args)
    except BaseException as e:  # (also SystemExit and KeyboardInterrupt)
        return f"{type(e).__name__}: {e}"
    return repr(r)


def timeout_for(gen):
    # a timeout acquire() takes: an int or a float, at the edges of PyTime_t's nanoseconds too
    k = gen.randrange(9)
    if k == 0:
        return gen.choice([-1, 0, 1, -2, 9223372036, 9223372037, -9223372036, -9223372037, True, False])
    if k == 1:
        return gen.choice([-1.0, 0.0, -0.0, -1e-9, -1e-10, -0.9999999999, -1.0000000001, 9223372036.854775, 9223372036.854776,
                           -9223372036.854775, -9223372036.854777, math.inf, -math.inf, math.nan, 1e300, 5e-324])
    if k == 2:
        return gen.randrange(-10, 10)
    if k == 3:
        return gen.randrange(-(2 ** 40), 2 ** 40)
    if k == 4:
        return gen.uniform(-3.0, 3.0)
    if k == 5:
        return math.ldexp(gen.random(), gen.randrange(-40, 40)) * gen.choice([1, -1])
    if k == 6:
        return float(gen.randrange(-(2 ** 34), 2 ** 34))
    if k == 7:
        return gen.choice([-1.0, -1])
    return math.ldexp(1.0, gen.randrange(30, 34)) * gen.choice([1, -1]) + gen.uniform(-2, 2)


def stack_valid(size):
    # Hosted twin of the private primitive; preserve the oracle's setting.
    # test_runtime_thread.py independently checks the actual native validator.
    previous = _thread.stack_size()
    try:
        _thread.stack_size(size)
        return 1
    except ValueError:
        return 0
    finally:
        _thread.stack_size(previous)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=20000)
    options = parser.parse_args()
    port = load("_thread_port", LIB / "_pystachy_thread.py")
    port.__pys_thread_stack_valid = stack_valid
    gen = random.Random(20261016)
    count = failures = 0

    def report(what, got, want):
        nonlocal failures
        failures += 1
        if failures <= 20:
            print(f"{what}: {got}, where CPython's is {want}")

    def same(what, got, want):
        nonlocal count
        count += 1
        if got != want:
            report(what, got, want)

    for r in range(options.rounds):
        # acquire() of an unlocked lock: True at once, or the error of its arguments
        blocking = gen.choice([True, False, 1, 0, "", "x", None])
        t = timeout_for(gen)
        args = (blocking, t) if gen.random() < 0.8 else (blocking,)
        same(f"lock.acquire{args!r}", outcome(port.allocate_lock().acquire, *args), outcome(_thread.allocate_lock().acquire, *args))
        same(f"RLock.acquire{args!r}", outcome(port.RLock().acquire, *args), outcome(_thread.RLock().acquire, *args))
        # acquire() of a locked lock without blocking, or with a timeout of 0
        a = port.allocate_lock()
        b = _thread.allocate_lock()
        a.acquire()
        b.acquire()
        args = gen.choice([(False,), (False, -1), (True, 0), (True, 0.0), (0,), (False, 0)])
        same(f"locked lock.acquire{args!r}", outcome(a.acquire, *args), outcome(b.acquire, *args))
        same("locked()", outcome(a.locked), outcome(b.locked))
        # an RLock's count, after some acquires and releases
        ra = port.RLock()
        rb = _thread.RLock()
        for i in range(gen.randrange(6)):
            if gen.random() < 0.6:
                same("RLock.acquire()", outcome(ra.acquire), outcome(rb.acquire))
            else:
                same("RLock.release()", outcome(ra.release), outcome(rb.release))
            same("RLock._recursion_count()", outcome(ra._recursion_count), outcome(rb._recursion_count))
            same("RLock._is_owned()", outcome(ra._is_owned), outcome(rb._is_owned))
        sa = outcome(ra._release_save)
        sb = outcome(rb._release_save)
        same("RLock._release_save()", sa.replace(str(port.get_ident()), "ID"), sb.replace(str(_thread.get_ident()), "ID"))
        if not sb.startswith("RuntimeError"):
            ra._acquire_restore(eval(sa))
            rb._acquire_restore(eval(sb))
            same("RLock._recursion_count() restored", outcome(ra._recursion_count), outcome(rb._recursion_count))
    # release() of an unlocked lock, and of an RLock not held
    same("lock.release()", outcome(port.allocate_lock().release), outcome(_thread.allocate_lock().release))
    same("RLock.release()", outcome(port.RLock().release), outcome(_thread.RLock().release))
    # stack_size(): the size before, which the call sets (0 restores the default)
    for size in [0, 1, 32767, 32768, 32769, 65536, 2 ** 40, 2 ** 62, -1, -(2 ** 40)]:
        same(f"stack_size({size})", outcome(port.stack_size, size), outcome(_thread.stack_size, size))
        same("stack_size()", outcome(port.stack_size), outcome(_thread.stack_size))
    # interrupt_main() of each signal number but SIGINT, whose handler raises KeyboardInterrupt, and
    # glibc's 32 and 33, which CPython reports as ignored (its handler is unknown)
    for signum in list(range(-3, 70)) + [2 ** 31 - 1, -(2 ** 31)]:
        if signum != 2 and signum != 32 and signum != 33:
            same(f"interrupt_main({signum})", outcome(port.interrupt_main, signum), outcome(_thread.interrupt_main, signum))
    same("interrupt_main()", outcome(port.interrupt_main), outcome(_thread.interrupt_main))
    same("TIMEOUT_MAX", repr(port.TIMEOUT_MAX), repr(_thread.TIMEOUT_MAX))
    same("error", repr(port.error), repr(_thread.error))
    same("_count()", outcome(port._count), outcome(_thread._count))
    same("exit()", outcome(port.exit), outcome(_thread.exit))
    # the C module's public names, signatures and docstrings
    for n in sorted(x for x in dir(_thread) if not x.startswith("__")):
        a = getattr(_thread, n)
        b = getattr(port, n, None)
        count += 1
        if b is None:
            report(n, "missing", "defined")
            continue
        if callable(a) and not isinstance(a, type):
            same(f"{n}.__doc__", (b.__doc__ or "").rstrip(), (a.__doc__ or "").rstrip())
            sig = a.__text_signature__
            if sig is not None:
                mine = str(inspect.signature(b)).split(" -> ")[0]
                for ann in (": int", ": float", ": bool"):
                    mine = mine.replace(ann, "")
                want = sig.replace("$module, ", "").replace("$module", "").replace("(, ", "(").replace("(/)", "()").replace("(/, ", "(")
                want = want.replace("kwargs={}", "kwargs=None").replace("signum=signal.SIGINT", "signum=2")
                same(f"{n} signature", mine.replace(" = ", "="), want)
    for cls, mine in ((_thread.LockType, port.LockType), (_thread.RLock, port.RLock)):
        for m in sorted(vars(cls)):
            if m.startswith("__"):
                continue
            count += 1
            if not hasattr(mine, m):
                report(f"{cls.__name__}.{m}", "missing", "defined")
                continue
            same(f"{cls.__name__}.{m}.__doc__", (getattr(mine, m).__doc__ or "").rstrip(), (getattr(cls, m).__doc__ or "").rstrip())
    same("lock.__doc__", port.LockType.__doc__, _thread.LockType.__doc__)
    same("_local.__doc__", port._local.__doc__, _thread._local.__doc__)
    same("_ExceptHookArgs.__doc__", port._ExceptHookArgs.__doc__, _thread._ExceptHookArgs.__doc__)
    same("__doc__", port.__doc__, _thread.__doc__)
    print(f"{count} checks, {failures} differ")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
