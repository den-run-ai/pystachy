# error: obj_index_nonint.py:8: error: __index__ returned non-int (type str)
# A subscript checks the type of what o.__index__() returns: CPython raises this TypeError there.
class Label:
    def __index__(self) -> str:
        return "one"


print([1, 2, 3][Label()])
