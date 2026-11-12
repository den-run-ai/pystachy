# error: set_optional_bool_lookup.py:4: error: a bool is looked up among int | None keys, which CPython finds as the int it equals: convert the bool with int()
# (a set[int] takes the bool as the int it equals; one whose elements may be None holds boxes)
s: set[int | None] = {None, 1}
print(True in s)
