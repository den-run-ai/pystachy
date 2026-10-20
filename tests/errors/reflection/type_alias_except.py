# error: type_alias_except.py:6: error: type alias 'Err' cannot be used as a value (only annotations may name it)
# (CPython raises TypeError: catching classes that do not inherit from BaseException is not allowed)
type Err = ValueError
try:
    raise ValueError("x")
except Err:
    print("caught")
