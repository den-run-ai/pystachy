# error: isinstance_type_of_value.py:6: error: isinstance() is only supported with the builtin types and classes as its second argument
# type(x) of a value that is no exception is no class object that Pystachy holds (CPython takes
# it): x's type decides, so the error stays isinstance()'s


print(isinstance(3, type(3)))
