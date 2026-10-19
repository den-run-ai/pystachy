# error: recursive_alias_union_class_eq.py:17: error: closed union operations require narrowing with isinstance() first
# == compares a recursive alias's values by descriptor, which holds only builtin values: a member
# holding objects (list[Foo]) needs narrowing, as it does in a union without a recursive alias.
type V = int | list[V]


class Foo:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other: object) -> bool:
        return True


a: list[int | list[Foo] | list[V]] = [[Foo(1)]]
b: list[int | list[Foo] | list[V]] = [[Foo(2)]]
print(a == b)
