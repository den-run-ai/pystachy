# error: type_statement_value.py:5: error: type alias 'IntList' cannot be used as a value (only annotations may name it)
# A type statement binds a TypeAliasType, whose __value__ is not supported; even type X = int
# is no int (CPython raises TypeError for IntList(...))
type IntList = list[int]
print(IntList.__value__)
