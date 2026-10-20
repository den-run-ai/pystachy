# Arbitrary integer-list reads check the current list after the index's effects, and keep
# negative indexing and the same caught errors. Both operands must be evaluated only once.
events: list[str] = []
xs = [10, 20, 30]


def target() -> list[int]:
    events.append("target")
    return xs


def index(i: int, grow: bool) -> int:
    events.append("index")
    if grow:
        xs.extend(list(range(100)))  # may replace the backing array after target() returned
    return i


def shrink() -> int:
    events.append("shrink")
    xs.clear()
    return 0


def get(o: list[int] | None, i: int) -> None:
    try:
        print("value", o[i])
    except IndexError as e:
        print("IndexError", str(e))
    except TypeError as e:
        print("TypeError", str(e))


for i in [0, 2, -1, -3, 3, -4, 9223372036854775807, -9223372036854775808]:
    get(xs, i)
get([], 0)
get([], -1)
get(None, 0)
print("bool indices", xs[False], xs[True])


def optional_index(o: list[int], i: int | None) -> None:
    try:
        print("optional index", o[i])
    except TypeError as e:
        print(str(e))


optional_index(xs, 1)
optional_index(xs, None)
print(target()[index(3, True)], events)
events.clear()
try:
    print(target()[shrink()])
except IndexError as e:
    print(str(e), events)
xs.extend([7, 8, 9])
events.clear()
print(target()[index(-1, False)], events)

# An index may rebind the name, but the evaluated target stays the original list.
def replace() -> int:
    global xs
    xs = [100]
    return 1


print(xs[replace()], xs)

# Bounds must be checked on each read even when previous reads in the same loop succeeded.
items = [1, 2, 3, 4]
for i in range(4):
    try:
        print("shrinking", items[i])
        items.pop()
    except IndexError as e:
        print(str(e))

# The slow path's exception must also preserve finally blocks and nested handlers.
try:
    try:
        get([42], -1)
        print(items[-9223372036854775808])
    finally:
        print("finally")
except IndexError as e:
    print("outer", str(e))

# Allocation during index evaluation keeps the already evaluated target alive under GC stress.
def allocated_index() -> int:
    garbage = [list(range(30)) for _ in range(40)]
    return len(garbage) // 20 - 1


print([11, 12, 13][allocated_index()])
