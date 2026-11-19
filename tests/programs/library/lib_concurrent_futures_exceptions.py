# What a submitted call raises is kept in its future, not raised by submit(): result() raises it,
# each time, and exception() returns it, the same object. That holds for a class of the program,
# a chained exception and SystemExit, which ends the program where result() raises it
import sys
from concurrent.futures import ThreadPoolExecutor


class AppError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__("code %d" % code)
        self.code = code


def risky(n: int) -> int:
    if n == 1:
        raise AppError(41)
    if n == 2:
        try:
            raise KeyError("inner")
        except KeyError as e:
            raise ValueError("outer") from e
    if n == 3:
        sys.exit(3)
    return n


with ThreadPoolExecutor(max_workers=2) as pool:
    fs = [pool.submit(risky, i) for i in range(4)]
print(fs[0].result(), fs[0].exception())
for attempt in range(2):
    try:
        fs[1].result()
    except AppError as e:
        print("AppError:", e, e.code, e is fs[1].exception())
try:
    fs[2].result()
except ValueError as e:
    print("ValueError:", e, type(e.__cause__).__name__)
r = repr(fs[2])
print(r[r.index(" state="):])
print([f.done() for f in fs], [f.cancelled() for f in fs])
print(type(fs[3].exception()).__name__)
print("before result()")
fs[3].result()
print("not reached")
