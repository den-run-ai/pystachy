# Items removed from a list become unreachable: pop, del, remove, clear and *= 0 leave no stale
# pointer in the list's array (pop(0) also leaves none behind the items it moves). A writer that
# only a removed item held is closed by CPython at once; Pystachy closes it when its path is
# opened again, so the read sees what the writer had buffered either way.
import os
from typing import TextIO


class Box:
    def __init__(self, f: TextIO):
        self.f = f


boxes: list[Box] = []


def add(tag: str) -> None:
    f = open(f"rt_list_vacated_{tag}.txt", "w")
    f.write(f"OLD {tag}")
    boxes.append(Box(f))


def scrub(n: int) -> int:
    # overwrites the dead stack frames below, so that only the list could still refer to a box
    a = n * 3
    b = a + 1
    if n == 0:
        return b
    return scrub(n - 1) * 7 % 1000003 + a - b


def remove(k: int) -> None:
    global boxes
    if k == 0:
        boxes.pop()
    elif k == 1:
        boxes.pop(0)
        boxes.pop()
    elif k == 2:
        del boxes[0]
        del boxes[-1]
    elif k == 3:
        boxes.remove(boxes[0])
        boxes.remove(boxes[-1])
    elif k == 4:
        boxes.clear()
    else:
        boxes *= 0


def check(k: int, tags: list[str]) -> None:
    for t in tags:
        add(t)
    remove(k)
    print(len(boxes), scrub(400))
    for t in tags:
        p = f"rt_list_vacated_{t}.txt"
        print(t, repr(open(p).read()))
        os.remove(p)


check(0, ["pop"])
check(1, ["pop0", "pop1"])
check(2, ["del0", "del1"])
check(3, ["remove0", "remove1"])
check(4, ["clear0", "clear1", "clear2"])
check(5, ["imul0", "imul1"])
