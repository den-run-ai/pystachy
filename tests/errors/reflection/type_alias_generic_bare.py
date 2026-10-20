# error: type_alias_generic_bare.py:5: error: generic type alias 'Pair' needs its type arguments here (Pair[T])
type Pair[T] = tuple[T, T]


def f(p: Pair) -> None:
    print(p)


f((1, 2))
