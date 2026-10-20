# A class of an imported module that Pystachy leaves uncompiled (for its Iterable[int] field or a
# nested class) still runs its body when the module is imported, as CPython does: a builtin
# operation there that raises makes the import raise, before the module's code after the class
# runs. Here 1 // 0, a missing key, int("x"), an index in a display, a method's default value and
# the body of a nested class raise. defmods/calm.py's classes raise nothing, and Pystachy evaluates
# none of the values of defmods/calm_*.py, which it computes otherwise than CPython (10**-1) or
# rejects (max(1, 2.5)).
try:
    from defmods import raise_zero
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
try:
    from defmods import raise_key
except KeyError as e:
    print("KeyError:", e)
try:
    from defmods import raise_conv
except ValueError as e:
    print("ValueError:", e)
try:
    from defmods import raise_index
except IndexError as e:
    print("IndexError:", e)
try:
    from defmods import raise_dictstar
except IndexError as e:
    print("dict unpacking IndexError:", e)
try:
    from defmods import raise_default
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
try:
    from defmods import raise_inner
except ValueError as e:
    print("ValueError:", e)
from defmods import calm, calm_bigfloat, calm_bigint, calm_bytes, calm_floor, calm_mixed, calm_pow, calm_shift

print(calm.after())
