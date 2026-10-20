# error: reflect_hasattr_exception.py:6: error: hasattr() of an exception object is not supported (#489)
# An exception object's class is known only at run time (its ExcClass), with no reflection record
try:
    raise ValueError("x")
except ValueError as e:
    print(hasattr(e, input()))
