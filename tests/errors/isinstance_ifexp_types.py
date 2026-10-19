# error: isinstance_ifexp_types.py:7: error: isinstance() is only supported with the builtin types and classes as its second argument
# A conditional expression of builtin types that are no exception classes is no class object that
# Pystachy holds (CPython takes it): its values decide, so the error stays isinstance()'s


flag = len("ab") > 1
print(isinstance(3, int if flag else str))
