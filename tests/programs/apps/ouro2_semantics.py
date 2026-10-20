from __future__ import annotations

# Corner cases of scoping, loops, lists and None, checked against CPython.


class Item:
    name: str
    tags: list[str]
    next: Item

    def __init__(self, name: str) -> None:
        self.name = name
        self.tags = []
        self.next = None

    def tag(self, t: str) -> Item:
        self.tags.append(t)
        return self


total = 0
limit = 3


def add(n: int) -> None:
    global total
    total += n


def shadow(limit: int) -> int:
    total = limit * 2  # parameter and local hide the globals
    return total


def find(items: list[Item], name: str) -> Item:
    for it in items:
        if it.name == name:
            return it
    return None


def first_big(rows: list[list[int]], floor: int) -> int:
    for r in rows:
        for v in r:
            if v > floor:
                return v
    return -1


def is_even(n: int) -> bool:
    if n == 0:
        return True
    return is_odd(n - 1)


def is_odd(n: int) -> bool:
    if n == 0:
        return False
    return is_even(n - 1)


def collatz(n: int) -> int:
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps


# loops
xs = [1, 2, 3]
seen = ""
for v in xs:  # the loop sees elements appended while it runs
    if v < 3:
        xs.append(v + 10)
    seen = seen + str(v) + " "
print(seen, len(xs))
for i in range(5):
    i = i * 10  # assigning the loop variable does not change the iteration
    seen = seen + str(i) + ","
print(seen, i)
k = 99
for k in range(3, 3):
    print("never")
print(k)
n = 4
count = 0
for j in range(n):  # range() is evaluated once
    n = 100
    count += 1
print(count, n, j)
out = ""
for a in range(4):
    for b in range(4):
        if b == a:
            continue
        if b > 2:
            break
        if a == 3:
            break
        out = out + str(a) + str(b) + " "
print(out)
w = 0
while True:
    w += 1
    if w % 2 == 0:
        continue
    if w > 6:
        break
print(w, first_big([[1, 2], [3, 40], [50]], 10), first_big([[1]], 10))

# scoping
add(5)
add(7)
print(total, shadow(4), total, limit, is_even(10), is_odd(7), collatz(27))

# lists and aliasing
grid = [[0] * 3] * 2  # both rows are the same list
grid[0][1] = 5
print(grid[1][1], grid[0] is grid[1], len([0] * 0), len([7] * -2))
rows: list[list[int]] = []
for r in range(2):
    rows.append([r] * 3)
rows[0][0] = 9
print(rows[0][0], rows[1][0], rows[0] is rows[1])
shared = [Item("s")] * 2
shared[0].tag("x")
print(len(shared[1].tags), shared[0] is shared[1])
copy = xs
copy.append(-1)
print(xs[-1], xs[-2], len(xs), xs.pop(), xs.pop(), len(copy))
stack: list[int] = []
for i in range(40):
    stack.append(i)
s = 0
while len(stack) > 20:
    s += stack.pop()
print(s, len(stack), stack[-1], stack[0])
bools = [True] * 3
bools[1] = False
bools.append(not bools[1])
print(bools[0], bools[1], bools[3], bools.pop(), len(bools))

# objects and None
items = [Item("a").tag("x").tag("y"), Item("b")]
items[0].next = items[1]
print(len(items[0].tags), items[0].next.name, items[1].next is None, find(items, "b").name, find(items, "z") is None)
maybe: Item = None
print(maybe is None, maybe == None, items[0] == items[0], items[0] != items[1], items[0].next == items[1])
maybe = find(items, "a")
maybe.name += "!"
maybe.tags[0] += "?"
print(items[0].name, items[0].tags[0], maybe is items[0])
nothing: list[Item] = [None, None]
nothing[1] = items[1]
print(nothing[0] is None, nothing[1].name, len(nothing))
empty: list[Item] = [None] * 3
print(len(empty), empty[2] is None)
