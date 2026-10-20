# Compiled exports in CPython's process pools, whose workers start by spawn (docs/concurrency.md):
# two workers that run at once, each with a runtime and heap of its own; results and exceptions as
# the module's source gives them; a clean shutdown; a worker killed in a compiled call; a Process
# whose target is an export; and the owner rule: only the thread that imported the module may call
# it, and a call refused to another thread runs none of its code. Each line is checked against the
# contract (tests/ffi/run.sh requires exit status 0) as well as compared with the source's run.
import concurrent.futures as cf
import multiprocessing as mp
import os
import threading
import pw


def expect(label, got, want):
    print(label, got)
    if got != want:
        raise SystemExit(f"{label} {got!r}, expected {want!r}")


def outcome(f):  # a future's result, or its exception as type and args (60 s at most)
    e = f.exception(60)
    return f.result() if e is None else (type(e).__name__, e.args)


def caught(f, *args):  # the exception a call raises, as type and args
    try:
        f(*args)
    except Exception as e:
        return type(e).__name__, e.args
    return None


def _init(barrier):  # (each worker, as it starts) where _meet's calls meet
    global _barrier
    _barrier = barrier


def _meet(_):  # (in a worker) a call, a wait for the other worker's call, a call
    first = pw.count()
    _barrier.wait(60)  # (a worker alone would raise BrokenBarrierError after 60 s)
    return pw.pid(), first, pw.count()


def refused(name):
    return f"{name}() is compiled by Pystachy, whose runtime is single-threaded: call it from the thread that imported its module"


def main():
    expect("owner:", pw.count(), 1)
    errs = []

    def other():
        try:
            pw.count()
        except RuntimeError as e:
            errs.append(str(e))

    t = threading.Thread(target=other)
    t.start()
    t.join()
    expect("thread:", errs, [refused("count")])
    with cf.ThreadPoolExecutor(1) as tp:
        expect("thread pool:", outcome(tp.submit(pw.count)), ("RuntimeError", (refused("count"),)))
        expect("before its argument:", outcome(tp.submit(pw.fib, "x")), ("RuntimeError", (refused("fib"),)))
    expect("owner again:", pw.count(), 2)  # (the refused calls counted nothing)
    expect("its argument:", caught(pw.fib, "x"), ("TypeError", ("'str' object cannot be interpreted as an integer",)))

    ctx = mp.get_context("spawn")
    with cf.ProcessPoolExecutor(2, mp_context=ctx, initializer=_init, initargs=(ctx.Barrier(2),)) as ex:
        met = [f.result(60) for f in [ex.submit(_meet, i) for i in range(2)]]
        expect("two workers at once:", len({p for p, _, _ in met} - {os.getpid()}), 2)
        expect("each counts its own calls:", [c for _, *c in met], [[1, 2], [1, 2]])
        expect("map:", list(ex.map(pw.fib, [10, 50, 90], timeout=60)), [55, 12586269025, 2880067194370816120])
        expect("map:", list(ex.map(pw.squares, [4, 0], timeout=60)), ["0,1,4,9", ""])
        expect("raises:", outcome(ex.submit(pw.check, -5)), ("ValueError", ("negative: -5",)))
        expect("raises:", outcome(ex.submit(pw.lookup, "key")), ("LookupError", ("no key",)))
        expect("exits:", outcome(ex.submit(pw.bye, 3)), ("SystemExit", (3,)))
        workers = mp.active_children()
        expect("workers after the errors:", len(workers), 2)
        expect("and they still work:", outcome(ex.submit(pw.check, 7)), 7)
    expect("after shutdown, exit codes:", sorted(p.exitcode for p in workers), [0, 0])
    expect("children left:", mp.active_children(), [])
    expect("then:", caught(ex.submit, pw.fib, 1), ("RuntimeError", ("cannot schedule new futures after shutdown",)))
    expect("the parent's own count:", pw.count(), 3)

    # a worker killed in a compiled call: that call and the one queued behind it fail, and the pool
    # takes no more work
    broken = "A process in the process pool was terminated abruptly while the future was running or pending."
    with cf.ProcessPoolExecutor(1, mp_context=ctx) as ex:
        killed, queued = ex.submit(pw.killed), ex.submit(pw.fib, 10)
        expect("killed:", outcome(killed), ("BrokenProcessPool", (broken,)))
        expect("queued:", outcome(queued), ("BrokenProcessPool", (broken,)))
        expect("then:", caught(ex.submit, pw.fib, 1), ("BrokenProcessPool", ("A child process terminated abruptly, the process pool is not usable anymore",)))
    expect("the parent's own count:", pw.count(), 4)

    # a Process whose target is an export: SystemExit's code is its exit status
    for f, args, code in [(pw.bye, (3,), 3), (pw.count, (), 0)]:
        p = ctx.Process(target=f, args=args)
        p.start()
        p.join(60)
        expect(f"Process({f.__name__}) exit code:", p.exitcode, code)


if __name__ == "__main__":
    main()
