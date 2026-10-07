from __future__ import annotations

# Sorting records three ways; each must agree, and the merge sort must be stable.


class Rec:
    key: int
    name: str

    def __init__(self, key: int, name: str) -> None:
        self.key = key
        self.name = name


def make(n: int) -> list[Rec]:
    out: list[Rec] = []
    seed = 12345
    for i in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        out.append(Rec(seed % 50, "r" + str(i)))
    return out


def merge_sort(a: list[Rec]) -> list[Rec]:
    if len(a) < 2:
        return a
    mid = len(a) // 2
    left: list[Rec] = []
    right: list[Rec] = []
    for i in range(len(a)):
        if i < mid:
            left.append(a[i])
        else:
            right.append(a[i])
    left = merge_sort(left)
    right = merge_sort(right)
    out: list[Rec] = []
    i = 0
    j = 0
    while i < len(left) or j < len(right):
        if j == len(right) or (i < len(left) and left[i].key <= right[j].key):
            out.append(left[i])
            i += 1
        else:
            out.append(right[j])
            j += 1
    return out


def sift(a: list[Rec], start: int, end: int) -> None:
    root = start
    while 2 * root + 1 < end:
        child = 2 * root + 1
        if child + 1 < end and a[child].key < a[child + 1].key:
            child += 1
        if a[root].key >= a[child].key:
            return
        t = a[root]
        a[root] = a[child]
        a[child] = t
        root = child


def heap_sort(a: list[Rec]) -> None:
    n = len(a)
    i = n // 2 - 1
    while i >= 0:
        sift(a, i, n)
        i -= 1
    end = n - 1
    while end > 0:
        t = a[0]
        a[0] = a[end]
        a[end] = t
        sift(a, 0, end)
        end -= 1


def insertion_sort(a: list[Rec]) -> None:
    for i in range(1, len(a)):
        v = a[i]
        j = i - 1
        while j >= 0 and a[j].key > v.key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = v


def keys(a: list[Rec]) -> str:
    s = ""
    for r in a:
        s = s + str(r.key) + " "
    return s


def stable(a: list[Rec]) -> bool:
    for i in range(1, len(a)):
        if a[i - 1].key == a[i].key and int(a[i - 1].name[1:]) > int(a[i].name[1:]):
            return False
    return True


recs = make(300)
m = merge_sort(recs)
h = make(300)
heap_sort(h)
ins = make(300)
insertion_sort(ins)
print(keys(m) == keys(h), keys(m) == keys(ins), stable(m), stable(ins), len(m))
print(keys(m)[:60], m[0].name, m[299].name, ins[0].name == m[0].name)
print(keys(merge_sort(make(1))), len(merge_sort(make(0))))
