# error: syntax_assign_debug_attr.py:3: error: cannot assign to __debug__
def f(x):
    x.__debug__ = 1


print("ran")
