# error: obj_float_nonfloat.py:8: error: Count.__float__ returned non-float (type int)
# float(o) checks the type of what o.__float__() returns: CPython raises this TypeError at the call.
class Count:
    def __float__(self) -> int:
        return 7


print(float(Count()))
