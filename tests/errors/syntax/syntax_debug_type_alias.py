# error: syntax_debug_type_alias.py:3: error: cannot assign to __debug__
def g(x):
    type __debug__ = int


print("ran")
