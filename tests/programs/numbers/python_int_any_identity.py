# pystachy: dynamic-any
# Typed aliases, calls, fields and cells must retain the originating wide object.
from typing import Any
from any_wide_values import Holder, closure, keep, keep_optional, make


def same(a: Any, b: Any) -> None:
    print(a is b, id(a) == id(b), a == b)


source = make(70)
alias = source
same(source, alias)
a: Any = source
same(a, source)
same(a, keep(source))
same(a, keep(a))
same(a, keep_optional(source))
independent: Any = make(70)
same(a, independent)
holder = Holder(source)
obj: Any = holder
same(a, holder.value)
same(a, holder.get())
same(a, obj.value)
same(a, obj.get())
obj.value = independent
same(independent, holder.value)
same(a, holder.value)
holder.set(source)
same(a, obj.value)
read = closure(source)
same(a, read())
held: list[Any] = [source, source, independent]
same(held[0], held[1])
same(held[0], held[2])
print(abs(a) is a, +a is a)


def default(value: Any = source) -> Any:
    return value


same(a, default())
source = -make(80)
same(a, default())
print(default(), source)
