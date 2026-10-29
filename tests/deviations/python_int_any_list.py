# pystachy: dynamic-any
# docs/python-int.md#64-bit-boundaries: imported promoting values remain typed, but a
# dynamic list display converts its items to Any and rejects values outside int64.
# CPython instead builds both wide lists; the exception belongs to the display.
from devmods.python_int_any_list import factorial

fits = factorial(0) * 9223372036854775807
print("fits", [fits, -fits - 1])

value = factorial(30)
print("typed", value)
try:
    print([value, value + 2])
except OverflowError as e:
    print("Any list:", e)

value = -value
print("typed negative", value)
try:
    print([value, value - 2])
except OverflowError as e:
    print("negative Any list:", e)
