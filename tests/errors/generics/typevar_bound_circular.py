# error: b.py:5: error: class 'tvcirc.a.Later' may not be defined where this TypeVar reads it through its module (as during a circular import): not supported (CPython raises AttributeError if it is not)
# A TypeVar's bound read through its module (tvcirc.a.Later) during a circular import, before that
# module's class statement has run, raises AttributeError in CPython, which Pystachy cannot check
# where it does not evaluate the bound.
import tvcirc.a

print("never")
