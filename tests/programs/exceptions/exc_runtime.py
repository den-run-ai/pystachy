# Exceptions the runtime raises, caught by except clauses: their classes, str() and repr()
import math
import os


def lookup(d: dict[str, int], k: str) -> int:
    return d[k]


d: dict[str, int] = {"a": 1}
xs = [1, 2, 3]
try:
    print(lookup(d, "a"), lookup(d, "zz"))
except KeyError as e:
    print("KeyError", e, repr(e))
try:
    print(xs[7])
except IndexError as e:
    print("IndexError", e, repr(e))
try:
    print(xs[1], xs[-9])
except LookupError as e:
    print("LookupError", e, repr(e))
try:
    n = int("x12")
except ValueError as e:
    print("ValueError", e, repr(e))
try:
    print(10 // (len(xs) - 3))
except ZeroDivisionError as e:
    print("ZeroDivisionError", e, repr(e))
try:
    print(1.5 / (len(xs) - 3))
except ArithmeticError as e:
    print("ArithmeticError", e, repr(e))
try:
    print(math.exp(1000.0))
except OverflowError as e:
    print("OverflowError", e, repr(e))
try:
    print(2.0 ** 10000)
except OverflowError as e:
    print("OverflowError", e, repr(e))
try:
    f = open("/nonexistent/dir/file.txt")
except FileNotFoundError as e:
    print("FileNotFoundError", e, repr(e))
try:
    os.remove("/nonexistent/x")
except OSError as e:
    print("OSError", e, repr(e))
try:
    a, b = xs
except ValueError as e:
    print("unpack", e)
try:
    s = "abc"
    print(s.index("z"))
except ValueError as e:
    print("str.index", e)
try:
    print(chr(-1))
except (TypeError, ValueError) as e:
    print("chr", e, repr(e))
try:
    xs.remove(42)
except Exception as e:
    print("remove", e)
try:
    print(d.pop("nope"))
except KeyError as e:
    print("pop", repr(e))
try:
    ys: list[int] = []
    ys.pop()
except IndexError as e:
    print("pop empty", e)
try:
    print(int("7") + int("8.5"))
except BaseException as e:
    print("BaseException", repr(e))
try:
    print(xs[10])
except:
    print("bare except")
print("end")
