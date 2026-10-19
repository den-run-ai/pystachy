# raise_cold: a function that cannot return, as each of its paths raises, is lowered cold and
# noinline (Gen.lower's raises_only), so that an error message it formats stays out of the checks
# LLVM inlines: raise_cold.attrs pins which functions are. Not one that may return, nor one with
# a loop, which might run until the program exits, nor a generator, nor the program's own code,
# which ends here by raising SystemExit
import sys


def out_of_range(i: int, n: int) -> None:
    raise IndexError(f"index {i} is out of range for {n} items")


def wrong(kind: int) -> int:
    if kind > 0:
        raise ValueError(f"kind {kind}")
    raise TypeError("no kind")


def checked(i: int, n: int) -> int:
    if i < 0 or i >= n:
        out_of_range(i, n)
    return i


def maybe(i: int) -> int:
    if i > 3:
        raise KeyError(i)
    return i * 2


def spin(i: int) -> None:
    while True:
        if i > 2:
            raise RuntimeError("spun")
        i += 1


def gen(n: int):
    yield n
    raise ValueError("generated")


class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def fail(self) -> None:
        raise AttributeError(f"box {self.v}")


def run() -> None:
    total = 0
    for k in range(5):
        try:
            total += checked(k, 4) + maybe(k)
        except IndexError as e:
            print(e)
        except KeyError as e:
            print("KeyError", e)
    for k in [1, 0]:
        try:
            wrong(k)
        except (ValueError, TypeError) as e:
            print(type(e).__name__, e)
    try:
        spin(0)
    except RuntimeError as e:
        print(e)
    try:
        Box(7).fail()
    except AttributeError as e:
        print(e)
    got: list[int] = []
    try:
        for v in gen(3):
            got.append(v)
    except ValueError as e:
        print(e, got)
    print(total, len(sys.argv) > 0)


run()
sys.exit(0)
