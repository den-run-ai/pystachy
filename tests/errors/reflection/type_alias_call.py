# error: type_alias_call.py:4: error: type alias 'Num' cannot be used as a value (only annotations may name it)
# (CPython raises TypeError: 'types.UnionType' object is not callable)
Num = int | float
print(Num(3))
