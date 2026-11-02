# A generator whose resume exceeds the recursion limit is finished, as CPython clears a frame
# whose entry fails: next(), send(), close() and throw() raise RecursionError, its finally
# block does not run, and it never resumes (#988). walk's body can recur, so each resume
# counts a frame; each probe resumes from the deepest frame's handler, already at the limit.
import sys
from collections.abc import Iterator


def walk(n: int) -> Iterator[int]:
    if n > 0:
        yield from walk(n - 1)
    try:
        yield n
        yield n + 60
    finally:
        print("finally", n)


def next_at_limit(g: Iterator[int]) -> str:
    try:
        return next_at_limit(g)
    except RecursionError:
        try:
            return "next: " + str(next(g))
        except RecursionError:
            return "next: RecursionError"


def send_at_limit(g: Iterator[int]) -> str:
    try:
        return send_at_limit(g)
    except RecursionError:
        try:
            return "send: " + str(g.send(None))
        except RecursionError:
            return "send: RecursionError"


def close_at_limit(g: Iterator[int]) -> str:
    try:
        return close_at_limit(g)
    except RecursionError:
        try:
            g.close()
            return "close: closed"
        except RecursionError:
            return "close: RecursionError"


def throw_at_limit(g: Iterator[int]) -> str:
    try:
        return throw_at_limit(g)
    except RecursionError:
        try:
            return "throw: " + str(g.throw(ValueError("thrown")))
        except RecursionError:
            return "throw: RecursionError"


def next_below_limit(g: Iterator[int]) -> str:
    # one frame below the limit: the outer body enters, and its delegate's entry fails
    try:
        r = next_below_limit(g)
    except RecursionError:
        return "deepest"
    if r != "deepest":
        return r
    try:
        return "next: " + str(next(g))
    except RecursionError:
        return "next: delegate RecursionError"


def after(g: Iterator[int]) -> None:
    try:
        print("then", next(g))
    except StopIteration:
        print("then finished")
    g.close()


original = sys.getrecursionlimit()
sys.setrecursionlimit(100)
g = walk(0)
print(next(g))
print(next_at_limit(g))
after(g)
g = walk(0)
print(next_at_limit(g))
after(g)
g = walk(0)
print(next(g))
print(send_at_limit(g))
after(g)
g = walk(0)
print(next(g))
print(close_at_limit(g))
after(g)
g = walk(0)
print(next(g))
print(throw_at_limit(g))
after(g)
g = walk(1)
print(next(g))
print(next_below_limit(g))
after(g)
# A generator resumed below the limit runs and finishes as usual.
g = walk(0)
print(next(g), next(g))
after(g)
sys.setrecursionlimit(original)
