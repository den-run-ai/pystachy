# Documented deviation: a ThreadPoolExecutor does not know that the program is ending
# (lib/compatibility.md#concurrentfutures), so submit() from an atexit callback runs the call
# and this prints 2 and 3. CPython has stopped its pools' worker threads by then, and its
# submit() raises RuntimeError: cannot schedule new futures after shutdown
import atexit
from concurrent.futures import ThreadPoolExecutor

pool = ThreadPoolExecutor(max_workers=1)


def last() -> None:
    try:
        print(pool.submit(len, "abc").result())
    except RuntimeError as e:
        print("RuntimeError:", e)


atexit.register(last)
print(pool.submit(len, "ab").result())
