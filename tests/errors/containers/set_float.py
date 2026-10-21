# error: set_float.py:3: error: set elements must be int or str, objects, or tuples of int, bool, str, str | None and objects, not float
# (a set's elements are what a dict's keys may be)
s = {1.5, 2.5}
print(s)
