# collections.abc.Set[T] is a set[T] while a program gives it only sets, as it always was: its
# value is changed, printed and tested as the set it is
from collections.abc import Set as AbstractSet


def grow(s: AbstractSet[str]) -> None:
    s.add("x")
    s |= {"y"}
    print(s == {"a", "x", "y"}, isinstance(s, set), type(s).__name__, len(s))


t = {"a"}
grow(t)
print(sorted(t), [1] if t else [0])
u: AbstractSet[int] = {3}
print(u, repr(u))
