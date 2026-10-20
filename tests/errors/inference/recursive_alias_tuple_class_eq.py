# error: recursive_alias_tuple_class_eq.py:19: error: closed union operations require narrowing with isinstance() first
# A tuple beside a recursive alias's value may hold a union of classes, which == cannot compare
# by descriptor either.
type V = int | list[V]


class A:
    def __init__(self, x: int) -> None:
        self.x = x


class B:
    def __init__(self, x: int) -> None:
        self.x = x


left: list[tuple[A | B, V]] = [(A(1), 2)]
right: list[tuple[A | B, V]] = [(A(1), 2)]
print(left == right)
