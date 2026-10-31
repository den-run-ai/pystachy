# pystachy: dynamic-any
# pystachy: python-int
# Both opt-ins: dynamic arithmetic promotes from small operands, then demotes exactly.
from typing import Any

a: Any = 9223372036854775807
b: Any = 1
wide: Any = a + b
print(wide, type(wide).__name__, wide - b, wide + a)
negative: Any = -wide
print(negative - b, -negative, abs(negative), negative // -b)
print(a * a, b << 70, 3 ** (b + 40))
print((wide - wide) + b, (wide >> 63) - b, ~wide)
parsed: Any = int("1180591620717411303424")
print(parsed, int(parsed), float(parsed), type(parsed) is int)
print(int("-1180591620717411303424"), int(1e30))
flag: Any = True
print(flag & flag, flag | False, flag ^ flag, flag + flag)
print(isinstance(parsed, int), isinstance(flag, int), type(flag) is bool)


class Integer:
    def __int__(self) -> int:
        print("int method")
        return 2 ** 80

    def __index__(self) -> int:
        print("unwanted index")
        return 1


class Index:
    def __index__(self) -> int:
        print("index method")
        return -2 ** 80


source: Any = Integer()
print(int(source))
source = Index()
print(int(source))
try:
    enormous: Any = 2 ** 2000
    print(float(enormous))
except OverflowError:
    print("float overflow")
try:
    print(wide << -parsed)
except ValueError:
    print("negative shift")
try:
    print(int("9" * 4301))
except ValueError:
    print("digit limit")
