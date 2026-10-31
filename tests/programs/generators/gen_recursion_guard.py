# Generator suspension must release recursion depth, and resumption reacquire it.
# Recursive yield-from is bounded at 100 levels even without native guards (#988).
import sys
from collections.abc import Generator, Iterator


def sequence(n: int) -> Iterator[int]:
    for i in range(n):
        yield i


def chain(n: int) -> Iterator[int]:
    if n == 0:
        yield 7
        return
    yield from chain(n - 1)


def depth(n: int) -> int:
    if n == 0:
        return 0
    return 1 + depth(n - 1)


def resume(n: int, generator: Iterator[int]) -> int:
    if n == 0:
        return next(generator)
    return resume(n - 1, generator)


def recovering() -> Generator[int, None, None]:
    try:
        for attempt in range(3):
            try:
                depth(100)
            except RecursionError:
                yield depth(3)
    except ValueError:
        yield depth(4)
    finally:
        print("generator cleanup", depth(2))


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
# Suspended generators and repeated yields must not consume active depth.
generators = [sequence(2) for i in range(100)]
total = 0
for generator in generators:
    total += next(generator)
print(total, depth(3))
for generator in generators:
    total += next(generator)
    generator.close()
print(total, depth(3))
print(sum(sequence(200)), depth(3))
# A resume records its current caller's depth, not the one at the prior yield.
stored = sequence(4)
print(resume(20, stored), depth(40))
print(next(stored), depth(40))
print(resume(10, stored), depth(40))
print(next(stored), depth(40))
stored.close()
# A handler inside a generator restores its own active depth. Yielding while
# handling an exception must also release that depth before a different resumer.
recovery = recovering()
print(next(recovery), depth(40))
print(resume(20, recovery), depth(40))
print(recovery.throw(ValueError("resume")), depth(40))
recovery.close()
print(depth(40))
for attempt in range(3):
    try:
        print(list(chain(100)))
    except RecursionError:
        print("generator caught")
    print(list(chain(3)), depth(3))
sys.setrecursionlimit(original)
