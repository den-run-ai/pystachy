# pystachy: python-int
# Documented 64-bit Any boundary (docs/python-int.md#64-bit-boundaries): storing a wide
# promoting int in a field must succeed, but reading that field through Any raises.
# CPython instead returns the wide int; the exception belongs to the read, not the store.
from devmods.python_int_any_field import read


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


box = Box(2 ** 70)
print("stored", box.value)
try:
    print(read(box))
except OverflowError as e:
    print("Any field:", e)
box.value = -2 ** 70
print("stored negative", box.value)
try:
    print(read(box))
except OverflowError as e:
    print("negative Any field:", e)
box.value = int("15000")
print("fits again", read(box))
