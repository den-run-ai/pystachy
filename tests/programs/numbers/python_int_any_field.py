# pystachy: python-int
# Wide promoting fields stay exact when another module reads them through Any.
from any_field_reader import read


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
