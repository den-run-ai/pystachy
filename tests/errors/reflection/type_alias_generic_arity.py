# error: type_alias_generic_arity.py:5: error: type alias 'Pair' takes 1 type argument (T), not 2
type Pair[T] = tuple[T, T]


def f(p: Pair[int, str]) -> None:
    print(p)


f((1, 2))
