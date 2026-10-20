# error: type_alias_variadic.py:6: error: type alias 'Row' with a TypeVarTuple (*Ts) or ParamSpec (**P) parameter is not supported with type arguments: write its value out
# (CPython substitutes the unpacked arguments: Row[int, str] is tuple[int, str])
type Row[*Ts] = tuple[*Ts]


def f(r: Row[int, str]) -> str:
    return r[1] * r[0]


print(f((2, "a")))
