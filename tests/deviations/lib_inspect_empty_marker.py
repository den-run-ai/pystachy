# Documented deviation (lib/compatibility.md#inspect): Parameter.empty, Signature.empty and
# inspect._empty are one marker object of a private class, where CPython's is a class, as a
# class is no value here. Its repr() and identity are CPython's; its type is not: CPython prints
# type and True, as its marker is a class.
import inspect

empty = inspect.Parameter.empty
print(repr(empty), empty is inspect.Signature.empty, empty is inspect._empty)
print(type(empty).__name__, type(empty).__name__ == "type")
