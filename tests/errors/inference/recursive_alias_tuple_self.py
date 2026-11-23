# error: recursive type aliases are not supported: 'V' refers to itself
# A tuple leaf does not hold the alias itself: only a list or a dict does (CPython prints 1)
type V = int | tuple[V, V] | list[V]


def f(v: V) -> None:
    print(v)


f(1)
