# error: type_alias_mutual.py:6: error: recursive type aliases are not supported: 'A' refers to itself
type A = list[B]
type B = dict[str, A]


def f(a: A) -> None:
    print(a)


f([])
