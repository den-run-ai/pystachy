"""List operations whose runtime functions moved to runtime.py. The lists are built before timing where a case only reads them."""
import sys
from time import perf_counter


def append_ints(n: int) -> int:
    # appends to one list of ints that is cleared every 4,096 items: growth from the least capacity
    total = 0
    xs: list[int] = []
    for i in range(n):
        xs.append(i)
        if len(xs) == 4096:
            total += xs[i & 4095]
            xs.clear()
    return total + len(xs)


def append_strs(n: int, words: list[str]) -> int:
    # a scanned list: inline items first, then an array of its own
    total = 0
    xs: list[str] = []
    for i in range(n):
        xs.append(words[i & 255])
        if len(xs) == 48:
            total += len(xs[i & 31])
            xs.clear()
    return total + len(xs)


def short_lists(n: int) -> int:
    # many lists of three items each, as a compiler's operand lists are
    total = 0
    for i in range(n):
        xs = [i, i + 1]
        xs.append(i + 2)
        total += xs[1] + len(xs)
    return total


def pop_push(n: int) -> int:
    # a stack: two pushes and a pop, then a pop
    total = 0
    xs: list[int] = [0]
    for i in range(n):
        xs.append(i)
        xs.append(i + 1)
        total += xs.pop()
        total += xs.pop()
    return total + len(xs)


def pop_front(n: int) -> int:
    # a queue of 64 items: pop(0) moves the rest
    total = 0
    xs: list[int] = [j for j in range(64)]
    for i in range(n):
        total += xs.pop(0)
        xs.append(i)
    return total


def insert_front(n: int) -> int:
    total = 0
    xs: list[int] = []
    for i in range(n):
        xs.insert(i & 1, i)
        if len(xs) == 64:
            total += xs[5]
            xs.clear()
    return total + len(xs)


def slices(n: int, xs: list[int]) -> int:
    total = 0
    for i in range(n):
        lo = i & 63
        ys = xs[lo : lo + 24]
        total += ys[i & 15] + len(ys)
    return total


def stepped(n: int, xs: list[int]) -> int:
    total = 0
    for i in range(n):
        ys = xs[i & 7 :: 5]
        total += ys[i & 7] + len(ys)
    return total


def extend_lists(n: int, xs: list[int]) -> int:
    total = 0
    ys: list[int] = []
    for i in range(n):
        ys.extend(xs)
        if len(ys) >= 2048:
            total += ys[i & 1023]
            ys.clear()
    return total + len(ys)


def reverse_copy(n: int, xs: list[int]) -> int:
    total = 0
    for i in range(n):
        ys = xs.copy()
        ys.reverse()
        total += ys[i & 127]
    return total


def indexed(n: int, xs: list[int]) -> int:
    # checked reads and writes by a varying index, negative ones too
    total = 0
    m = len(xs)
    for i in range(n):
        j = (i * 7) % m
        xs[j - m] = xs[j] + 1
        total += xs[-1 - j]
    return total


kind = sys.argv[1]
n = int(sys.argv[2])
words = ["w" + str(i) for i in range(256)]
nums = [(i * 16411) % 65537 for i in range(128)]
start = perf_counter()
if kind == "list-append":
    result = append_ints(n)
elif kind == "list-append-str":
    result = append_strs(n, words)
elif kind == "list-short":
    result = short_lists(n)
elif kind == "list-stack":
    result = pop_push(n)
elif kind == "list-pop-front":
    result = pop_front(n)
elif kind == "list-insert":
    result = insert_front(n)
elif kind == "list-slice":
    result = slices(n, nums)
elif kind == "list-slice-step":
    result = stepped(n, nums)
elif kind == "list-extend":
    result = extend_lists(n, nums)
elif kind == "list-reverse":
    result = reverse_copy(n, nums)
elif kind == "list-index":
    result = indexed(n, nums)
else:
    raise ValueError("unknown workload")
elapsed = perf_counter() - start
print(result, elapsed)
