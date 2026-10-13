# error: union_method.py:4: error: 'int | str' has no method 'upper': narrow it to one of its types first, with isinstance()
# a method of one member: CPython raises AttributeError where x holds an int
def f(x: int | str) -> str:
    return x.upper()


print(f("a"))
