# pystachy: dynamic-any
# A dynamic list display boxes imported promoting values without narrowing them.
from any_list_producer import factorial

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
