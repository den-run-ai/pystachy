# Raises inside runtime.py (str, math and format functions written in the subset) unwind
# through its frames to the program's handlers, JIT and AOT (#27).
import math


def find_it(s: str, sub: str) -> int:
    return s.index(sub)


def fmt(v: int, spec: str) -> str:
    return format(v, spec)


def run() -> None:
    try:
        print("abc".index("z"))
    except ValueError as e:
        print("index:", e)
    try:
        find_it("hello", "q")
    except ValueError as e:
        print("index in a function:", e)
    try:
        print(math.comb(-1, 2))
    except ValueError as e:
        print("comb:", e)
    try:
        print(math.isqrt(-4))
    except ValueError as e:
        print("isqrt:", e)
    try:
        print(fmt(3, "q"))
    except ValueError as e:
        print("format:", e)
    try:
        print("x".center(5, "ab"))
    except TypeError as e:
        print("center:", e)
    try:
        print("a,b".split(""))
    except ValueError as e:
        print("split:", e)
    try:
        print("abc".rindex("z", 1))
    except ValueError as e:
        print("rindex:", e)
    try:
        print("a\tb".expandtabs(2**40))
    except (OverflowError, MemoryError) as e:
        print("expandtabs:", type(e).__name__)
    n = 0
    for i in range(1000):
        try:
            n += "abcdef".index("f" if i % 2 else "g")
        except ValueError:
            n -= 1
    print("loop:", n)


run()
try:
    "abc".index("z")
finally:
    print("finally ran")
