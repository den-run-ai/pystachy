# error: set_optional_int_mixed.py:5: error: unsupported operand types for |: set[int] and set[int | None] (a set holds elements of one type)
# (an int | None element is a box, which an int element is not: no table holds both as they are)
a: set[int] = {1}
b: set[int | None] = {None, 2}
print(a | b)
