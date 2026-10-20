# error: too many arguments for popitem()
# (CPython raises TypeError: dict.popitem() takes no arguments (1 given))
d = {1: 2}
print(d.popitem(1))
