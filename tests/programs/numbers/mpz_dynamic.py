# pystachy: dynamic-any
# Original integration coverage for the existing user-class Dynamic Any dispatch.
# The bigint payload remains an opaque pointer-bearing field of a class object.
from typing import Any
try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz

x: Any = mpz("18446744073709551616")
y: Any = mpz(3)
print(x + y, x * y, x // y, x % y)
assert str(x + 7) == "18446744073709551623"
assert str(-x) == "-18446744073709551616"
assert str(~x) == "-18446744073709551617"
assert x == mpz("18446744073709551616") and x != y
assert bool(x) and not bool(mpz(0))
print("dynamic hash", hash(x), "text", str(x))
items: list[Any] = [x, y]
lookup: dict[Any, str] = {x: "large", y: "small"}
for i in range(40):
    scratch: Any = mpz(1) << (128 + i)
    assert bool(scratch)
assert lookup[mpz("18446744073709551616")] == "large"
assert lookup[mpz(3)] == "small"
print("dynamic storage", items[0] + items[1], len(lookup))
