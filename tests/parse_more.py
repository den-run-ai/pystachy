# Parsing and definite assignment corner cases: a multi-line expression in a triple-quoted
# f-string field, an escaped quote in a string inside a field, form feeds, an empty slice
# step, del of a tuple of names, valid syntax in code that never runs (starred targets,
# tuple subscripts with slices, async comprehensions, PEP 695 generics), a global statement
# in a branch a static test removes, untyped empty containers used before they are filled,
# and loops whose else block or body changes what is assigned.
x = 42
xs = [1, 2, 3]
print(f"""{x
+ 1} {xs
    [1:]} {x
    * 2:>8}""")
print(f"{'it\'s'}")
print(xs[1:3:], xs[::], "abcd"[:2:])


a = 1
b = 2
del (a, b)
c = 3
del c,


def never(rows, grid):
    for *head, last in rows:
        pass
    return grid[1:2, 3], grid[1,]


async def agen(it):
    return [v async for v in it]


def first[T](items: list[T]) -> T:
    return items[0]


g = 1


def setg(v):
    if isinstance(v, str):
        global g
    g = 2
    return v


setg(3)
print(g, first(["p", "q"]))


def unused() -> None:
    pass


history = []
snapshot = history.copy()
history.append("x")
print(snapshot, history)
acc = []


def grow() -> list[int]:
    global acc
    acc = [5]
    return [1]


acc += grow()
print(acc)


def find(ns: list[int]) -> int:
    total = 0
    for n in ns:
        if n < 0:
            break
        total += n
    else:
        total += 100
    return total


print(find([1, 2]), find([1, -1, 5]))
