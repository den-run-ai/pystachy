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
    # Overwrite dead allocation frames. Keep three checked scalars live across
    # the recursive call: LLVM 18's ARM64 frame for two leaves an untouched word
    # of alignment padding that can still contain a conservative File root.
    a = n * 3
    b = a + 1
    c = n * 5
    if n == 0:
        return b
    return scrub(n - 1) * 7 % 1000003 + a - b + c - c


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


def populate(tags: list[str], depth: int) -> int:
    # A non-tail recursive frame keeps creation out of check(): an inlined add
    # can leave its dead File in a callee-saved register until after the read.
    # listprobe also checks the vacated slots directly, independently of when
    # conservative roots disappear and files are finalized.
    if depth:
        return populate(tags, depth - 1) * 7 % 1000003
    for tag in tags:
        add(tag)
    return len(tags)


def check(k: int, tags: list[str]) -> None:
    count = populate(tags, 2)
    assert count == len(tags) * 49
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
