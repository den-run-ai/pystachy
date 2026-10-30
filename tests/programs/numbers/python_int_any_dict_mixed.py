# pystachy: dynamic-any
# Comparing stored values does not read them into a fixed-width local.
from typing import Any
from any_wide_values import make

wide = make(70)
typed: dict[int, int] = {wide: wide, -wide: -wide}
boxed: dict[Any, Any] = {wide: wide, -wide: -wide}
print(typed == boxed, boxed == typed, typed != boxed)
different: dict[Any, Any] = {wide: wide, -wide: wide}
print(typed == different, different == typed)

pair = (wide, -wide)
native_pairs: dict[str, tuple[int, int]] = {"pair": pair}
boxed_pairs: dict[Any, tuple[int, int]] = {"pair": pair}
print(native_pairs == boxed_pairs, boxed_pairs == native_pairs)


class Value:
    def __eq__(self, other: Any) -> bool:
        print("value callback", other)
        return other == wide


one: dict[int, int] = {wide: wide}
callback: dict[Any, Any] = {wide: Value()}
print(one == callback, callback == one)
