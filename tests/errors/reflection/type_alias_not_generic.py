# error: type_alias_not_generic.py:5: error: type alias 'Row' is not generic: it takes no type arguments
type Row = list[str]


def f(p: Row[int]) -> None:
    print(p)


f(["a"])
