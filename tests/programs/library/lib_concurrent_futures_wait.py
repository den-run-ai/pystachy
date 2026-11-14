# wait() and as_completed() of an executor's futures: the named tuple of the sets done and
# not_done, return_when, duplicates, a list, a set, a tuple and a dict of futures. The futures
# are all done once wait() has returned, so nothing depends on which call a worker ran first:
# what is printed is sorted
from concurrent.futures import (ALL_COMPLETED, FIRST_COMPLETED, FIRST_EXCEPTION,
                                ThreadPoolExecutor, as_completed, wait)
import concurrent.futures


def work(n: int) -> int:
    if n % 4 == 3:
        raise KeyError(n)
    return n * 10


with ThreadPoolExecutor(max_workers=3) as pool:
    fs = [pool.submit(work, i) for i in range(6)]
    r = wait(fs)
    print(type(r).__name__, len(r), len(r.done), len(r.not_done), r.not_done == set())
    done, not_done = wait(fs, return_when=ALL_COMPLETED)
    print(len(done), len(not_done), done == set(fs), fs[0] in done)
    print(sorted(f.result() for f in done if f.exception() is None))
    print(sorted(str(f.exception()) for f in done if f.exception() is not None))
    r2 = wait(fs, timeout=5, return_when=FIRST_EXCEPTION)
    print(len(r2.done), len(r2[0]), len(r2[1]))
    r3 = wait(fs + fs, 1.5, FIRST_COMPLETED)
    print(len(r3.done), len(r3.not_done))
    print(len(concurrent.futures.wait(set(fs)).done), len(wait((fs[0], fs[1])).done))
    got = []
    for f in as_completed(fs):
        if f.exception() is None:
            got.append(f.result())
    print(sorted(got))
    print(len(list(as_completed(fs + fs, timeout=10))))
    print(sum(1 for f in concurrent.futures.as_completed(fs) if f.done()))
    it = as_completed(fs[:1])
    print(next(it).result())
    try:
        next(it)
    except StopIteration:
        print("StopIteration")
    # (return_when is checked only where wait() has to wait)
    print(len(wait(fs, return_when="SOMETIME").done))
    # the documentation's example: a dict from each future to what it was submitted for
    future_to_n = {pool.submit(work, n): n for n in [8, 9, 10]}
    seen = []
    for future in as_completed(future_to_n):
        seen.append("%d: %d" % (future_to_n[future], future.result()))
    print(sorted(seen))
print(FIRST_COMPLETED, FIRST_EXCEPTION, ALL_COMPLETED)
