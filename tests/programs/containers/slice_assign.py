# Assignment to list slices, as CPython 3.13's list_ass_subscript: with a step of 1 any number of
# items replace the slice's (inserting where the slice is empty), with another step one for each
# (ValueError otherwise); the value is any iterable, taken before the bounds are clamped to the
# list's length, and a list assigned to a slice of itself is copied first. The value is evaluated
# before the list and the bounds, an iterator call or generator expression runs after them, and
# a step of 0 raises before any item is taken.
from typing import Iterator, NamedTuple, TypeVar

T = TypeVar("T")


def say(v: int) -> int:
    print("say", v)
    return v


xs = [0, 1, 2, 3, 4, 5]
xs[1:3] = [7, 8, 9, 10]
print(xs)
xs[2:6] = [5]
print(xs)
xs[4:4] = [6, 6]
print(xs)
xs[5:1] = [3]  # (an empty slice: inserted at its start)
print(xs)
xs[-100:1] = []
print(xs)
xs[100:200] = [99]
print(xs)
xs[:] = [1, 2, 3, 4, 5, 6, 7, 8]
print(xs)
xs[::2] = [0, 0, 0, 0]
print(xs)
xs[::-3] = [-1, -2, -3]
print(xs)
xs[6:1:-2] = [5, 5, 5]
print(xs)
xs[1:6:-1] = []
print(xs)
xs[::1] = [4, 5]  # (a step of 1 is a plain slice)
print(xs)
xs[None:None:None] = [6]
print(xs)
xs[:] = []
print(xs, len(xs))
xs[:] = [1]
xs[-9223372036854775807 - 1 : 9223372036854775807] = [2, 3]
print(xs)

for value, step in [([7], 2), ([7, 8, 9], 2), ([], 3), ([], -1), ([1, 2, 3], 0)]:
    ys = [1, 2, 3, 4]
    try:
        ys[::step] = value
        print("ok", ys)
    except ValueError as e:
        print("ValueError", e)

# a list assigned to a slice of itself is copied first
zs = [1, 2, 3, 4]
zs[1:2] = zs
print(zs)
zs[::-1] = zs
print(zs)
zs[::2] = zs[:4]
print(zs)
zs[:0] = zs
print(zs)

# any iterable: a str's characters, tuples, a dict's keys, a set, a runtime-length tuple, range(),
# map(), filter(), zip(), enumerate(), reversed() and generator expressions
cs = ["a", "b", "c"]
cs[1:2] = "xyz"
print(cs)
cs[::2] = ("p", "q", "r")
print(cs)
cs[:] = {"k": 1, "l": 2}
print(cs)
cs[3:] = {"m"}
print(cs)
cs[:1] = ()
print(cs)
ns = [0, 0, 0]
ns[1:] = range(3, 9, 2)
print(ns)
ns[::-1] = map(len, ["a", "bb", "ccc", "dddd"])
print(ns)
ns[:2] = filter(None, [0, 4, 0, 8])
print(ns)
ns[2:] = (n * n for n in ns if n > 2)
print(ns)
ns[:] = reversed(ns)
print(ns)
ps = [(0, "x")]
ps[1:] = enumerate("ab")
print(ps)
ps[:1] = zip([7], ["z"])
print(ps)


def counted(items: list[int]) -> tuple[int, ...]:
    return tuple(items)


ns[1:3] = counted([10, 20, 30])
print(ns)

# the value's items widen as list.extend() takes them: a list[str]'s into a list[str | None], and
# objects into a list of their base class's
os: list[str | None] = [None, "a"]
plain = ["b", "c"]
os[:1] = plain
print(os)
os[::2] = [None, None]
print(os, plain)


class Shape:
    def name(self) -> str:
        return "shape"


class Square(Shape):
    def name(self) -> str:
        return "square"


shapes = [Shape()]
squares = [Square(), Square()]
shapes[1:] = squares
print([s.name() for s in shapes])

# an object's items are taken by iterating it, as CPython's PySequence_Fast does: its __len__
# is not called (list() and list.extend() call it as a length hint)


class Bag:
    def __init__(self, items: list[int], fail: bool) -> None:
        self.items = items
        self.fail = fail

    def __iter__(self) -> Iterator[int]:
        print("iter")
        return iter(self.items)

    def __len__(self) -> int:
        print("len")
        if self.fail:
            raise RuntimeError("no len")
        return len(self.items)


bs = [1, 2, 3]
bs[1:] = Bag([5, 6], False)
print(bs)
bs[::2] = Bag([7, 8], True)
print(bs)

# a generator that changes the list: the bounds are clamped to the length it leaves
gs = [1, 2, 3, 4]


def grow(x: int) -> int:
    gs.append(x)
    return x


gs[-1:] = (grow(x) for x in [7, 8])
print(gs)
try:
    gs[5::2] = (grow(x) for x in [5])  # (one item of 7, two once the generator has run)
except ValueError as e:
    print("ValueError", e)
print(gs)

# evaluation order: the value, the list, the bounds; a generator's items after them
order = [1, 2, 3, 4, 5]


def items() -> list[int]:
    print("items")
    return [8, 9]


def target() -> list[int]:
    print("target")
    return order


target()[say(1) : say(3)] = items()
print(order)
target()[say(4) : say(0) : say(-2)] = (say(x) for x in [6, 7])
print(order)
try:
    target()[say(0) : say(4) : say(0)] = (say(x) for x in [5, 6])
except ValueError as e:
    print("ValueError", e)
print(order)

# None: the list's TypeError once the bounds are evaluated; a value that is None
maybe: list[int] | None = None
try:
    maybe[say(0) : say(1)] = [1]
except TypeError as e:
    print("TypeError", e)
try:
    maybe[say(0) : say(1)] = (say(x) for x in [1])
except TypeError as e:
    print("TypeError", e)
nothing: list[int] | None = None
for step in [1, 2, 0]:
    try:
        order[::step] = nothing
    except (TypeError, ValueError) as e:
        print(type(e).__name__, e)


class Point(NamedTuple):
    x: int
    y: int


def no_point() -> Point | None:
    return None


def no_bag() -> Bag | None:
    return None


for step in [1, 2, 0]:
    try:
        order[::step] = no_point()
    except (TypeError, ValueError) as e:
        print(type(e).__name__, e)
    try:
        order[::step] = no_bag()
    except (TypeError, ValueError) as e:
        print(type(e).__name__, e)

# range(): its arguments are evaluated first, its items made once the list and the bounds are
# (a step of 0 raises before a huge range would be)
try:
    order[::0] = range(2**60)
except ValueError as e:
    print("ValueError", e)
try:
    maybe[0:1] = range(say(2**60))
except TypeError as e:
    print("TypeError", e)
order[say(0) : say(2)] = range(say(3))
print(order)

# xs[a:b] op= v: the slice, extended or repeated, stored back
ag = [1, 2, 3, 4]
ag[1:3] += [7]
print(ag)
ag[:2] *= 2
print(ag)
ag[::2] += []
print(ag)
try:
    ag[::2] += [0]
except ValueError as e:
    print("ValueError", e)
print(ag)
try:
    maybe[0:1] += [1]
except TypeError as e:
    print("TypeError", e)

# targets in for loops and chains, fields, nested lists, closures, methods and templates
fs = [1, 2, 3]
for fs[0:1] in [[4, 5], [6]]:
    print(fs)
a = fs[1:] = [9]
print(a, fs)
grid = [[1, 2, 3], [4, 5, 6]]
grid[1][::2] = [0, 0]
grid[:1] = [[7]]
print(grid)


class Stack:
    def __init__(self) -> None:
        self.items: list[str] = []

    def push_all(self, more: list[str]) -> None:
        self.items[len(self.items) :] = more

    def reverse_top(self, n: int) -> None:
        def flip() -> None:
            self.items[-n:] = self.items[: -n - 1 : -1]

        flip()


st = Stack()
st.push_all(["a", "b", "c", "d"])
st.reverse_top(3)
print(st.items)


def splice(xs: list[T], at: int, more: list[T]) -> list[T]:
    xs[at:at] = more
    return xs


print(splice([1, 2], 1, [5, 6]), splice(["x"], 0, ["y"]), splice([[1]], 1, [[2]]))

# a key function that changes the list being sorted
srt = [3, 1, 2]


def key(x: int) -> int:
    srt[0:0] = [0]
    return x


try:
    srt.sort(key=key)
except ValueError as e:
    print("ValueError", e)
print(srt)
srt2 = [3, 1, 2]


def key2(x: int) -> int:
    srt2[:] = []
    return x


srt2.sort(key=key2)
print(srt2)

# an empty list's first slice assignment types it, as list.extend() does, also where the list is
# read before it and the value is a generator expression, map() or an iterator call
inferred = []
inferred[:] = ["p", "q"]
print(inferred)


def fill(ys: list[int]) -> None:
    xs = []
    print(len(xs))
    xs[len(xs) :] = (y * 2 for y in ys)
    rs = []
    print(rs)
    rs[:] = range(3)
    ms = []
    print(ms)
    ms[0:0] = map(str, ys)
    es = []
    print(es)
    es.extend(y + 1 for y in ys)
    print(xs, rs, ms, es)


fill([1, 2])

# ... where a function fills a global list that another reads first, where a loop over the empty
# *args or a branch the types remove would fill it, and from a tuple, set, str, dict or object
LOADED = []


def show() -> None:
    print(LOADED)


def load() -> None:
    LOADED[:] = [1, 2]


show()
load()
show()


def gather(*args: int) -> list[int]:
    ys = []
    for x in args:
        ys[:0] = [x]
    return ys


def pick(x: int | str) -> list[int]:
    zs = []
    if isinstance(x, str):
        zs[:] = [len(x)]
    return zs


print(gather(), gather(1, 2), pick(3), pick("ab"))
t1 = []
t1[:] = (1, 2)
t2 = []
t2[:] = {3}
t3 = []
t3[:] = "ab"
t4 = []
t4[:] = {"k": 1}
t5 = []
t5[:] = Point(4, 5)
print(t1, t2, t3, t4, t5)

# an empty list assigned to a slice of a call's result, whose type is not known before it
held = [[1, 2, 3], [4, 5]]


def row(i: int) -> list[int]:
    return held[i]


row(0)[:1] = []
row(1)[:] = []
print(held)
