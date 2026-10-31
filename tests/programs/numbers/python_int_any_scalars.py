# pystachy: dynamic-any
# Wide ints use Python's numeric semantics after crossing an Any boundary.
from typing import Any
from any_wide_values import keep, keep_optional, make

a: Any = make(70)
b: Any = -make(70)
small: Any = 17
flag: Any = True
print(a, b, repr(a), str(b), bool(a), bool(b))
print(type(a) is int, type(b).__name__, type(a) is type(small))
print(isinstance(a, int), isinstance(a, bool), isinstance(flag, int), type(flag) is bool)
print(keep(a), keep(b), keep_optional(a), keep_optional(None))
print(float(a), float(b), hash(a), hash(b))
print(a + 7, 7 + a, b - 7, 7 - b, a * 3, 3 * b)
print(a // 3, b // 3, a % 3, b % 3)
print(a & 255, a | 255, a ^ 255, a << 3, b >> 3)
print(-a, +a, ~a, abs(b), abs(a) is a, +a is a)
print(a / make(70), a ** -1, small ** 2)
print(a - a, (a - a) + 1, a >> 70, b >> 200)
print(a == float(a), a != float(a), a < float(a), a <= float(a))
print(a > float(a), a >= float(a), float(a) == a, float(a) < a)
near: Any = a + 1
print(near == float(a), near > float(a), float(a) < near)
print(b == -float(a), b < -float(a), b <= -float(a), -float(a) >= b)
print(a == small, a > small, b < small, a == flag, a > flag)
nan: Any = float("nan")
print(a == nan, a != nan, a < nan, a <= nan, a > nan, a >= nan)
print(nan == a, nan != a, nan < a, nan <= a, nan > a, nan >= a)
print(a == float("inf"), a < float("inf"), b > -float("inf"))
edge: Any = make(63)
print(edge - 1, -edge, edge == float(edge), edge - 1 == float(edge))
