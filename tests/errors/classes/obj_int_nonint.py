# error: obj_int_nonint.py:8: error: __int__ returned non-int (type str)
# int(o) checks the type of what o.__int__() returns: CPython raises this TypeError at the call.
class Label:
    def __int__(self) -> str:
        return "seven"


print(int(Label()))
