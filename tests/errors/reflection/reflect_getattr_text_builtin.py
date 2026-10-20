# error: reflect_getattr_text_builtin.py:7: error: the text of getattr(o, name) for a run-time name is not supported where o may be a int, whose methods are no values (#247, #489)
x: int | None = 5
n = input()
print(hasattr(x, n))
# (hasattr is: the text of a builtin value's attributes, its methods among them, is not, which is
# a compile-time error rather than a crash of the compiler)
print(getattr(x, n, None))
