# error: '_EmptyType' object is not callable
# Parameter.empty is a marker object, where CPython's is a class, which a call makes an object of
import inspect

print(inspect.Parameter.empty())
