# Cloned range loops keep field-address effects and report folded read guards.
class Box:
    def __init__(self) -> None:
        self.value = 0


def copy(xs: list[int], ys: list[int], box: Box, n: int) -> None:
    for i in range(n):
        box.value = xs[i]
        ys[i] = box.value


def total(xs: list[int], box: Box, n: int) -> None:
    for i in range(n):
        box.value += xs[i]


box = Box()
ys = [0, 0]
copy([3, 4], ys, box, 2)
print(ys, box.value)
total([1, 2], box, 2)
print(box.value)
try:
    copy([5, 6], ys, box, 3)
except IndexError:
    print("read bound", ys, box.value)
try:
    copy([7, 8], [0], box, 2)
except IndexError:
    print("write bound", box.value)
copy([], [], box, 0)
print("empty", box.value)
