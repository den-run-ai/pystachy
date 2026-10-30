# pystachy: dynamic-any
# pystachy: python-int
from typing import Any
import mods.wide_literal_identity as peer


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def literal() -> int:
    return 1180591620717411303424


def boxed_literal() -> Any:
    return 1180591620717411303424


def magnitude(value: int) -> int:
    return abs(value)


first = 1180591620717411303424
second = 1180591620717411303424
same("same literals", first, second)
same("typed returns", literal(), literal())
same("boxed returns", boxed_literal(), boxed_literal())
same("return and global", literal(), first)
same("hexadecimal", first, 0x400000000000000000)
same("octal", first, 0o200000000000000000000000)
same("binary", first, 0b10000000000000000000000000000000000000000000000000000000000000000000000)
same("negative", -1180591620717411303424, -0x400000000000000000)
same("separate modules", first, peer.VALUE)
same("imported return", peer.VALUE, peer.literal())
same("separate module return", first, peer.literal())
same("runtime power", first, 2 ** 70)
computed = int("1180591620717411303424")
independent = int("1180591620717411303424")
negative = -computed
same("computed objects", computed, independent)
same("arguments min first equal", min(computed, independent), computed)
same("arguments max first equal", max(independent, computed), independent)
same("arguments min", min(first, computed, negative), negative)
same("arguments max", max(-first, computed, first), computed)
same("unary plus", computed, +computed)
same("positive abs", computed, abs(computed))
same("returned abs", computed, magnitude(computed))
same("negative unary plus", negative, +negative)
same("negative abs creates object", abs(negative), abs(negative))
small = int("13000")
same("small positive abs", small, magnitude(small))
same("nested small sign", -(500 + 500), -1000)
values: list[int] = [first, 1180591620717411303424, literal()]
for value in values:
    same("stored constant", value, first)
print(18446744073709551615, 18446744073709551616, -18446744073709551616)
print(123456789012345678901234567890123456789012345678901234567890)
