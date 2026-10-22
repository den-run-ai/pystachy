# pystachy: dynamic-any
# Static argument unpacking shares the direct method dispatcher. CPython's direct bool method
# arity error names int.bit_count(), but its unpacked call's bound method names bool.bit_count().
# The exception type and argument effects agree; the error's receiver name still differs.
from typing import Any


def side() -> int:
    print("argument")
    return 1


x: Any = True
try:
    x.bit_count(*(side(),))
except TypeError as err:
    print(err)
