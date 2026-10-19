# *args tuples that a call makes in its own frame (Gen.stack_tuple): each way a function can keep
# its *args, or a local assigned them, past the call gets a tuple that outlives the call, equal to
# what was passed, and the same tuple wherever one call kept it; so does a generator expression that
# reads them as it is iterated, after the call. A lookup or a read keeps nothing
from functools import cache

saved: list[tuple[int, str]] = []
index: dict[tuple[int, str], int] = {}
seen: set[tuple[int, str]] = set()


def store(*args):
    return args


def stored(*args):
    out = [args]
    out.append(args)
    return out


def aliased(*args):
    key = args
    out: list[tuple[str, str]] = []
    out.append(key)  # (key's copy first)
    out.append(args)  # (then args': the same tuple)
    return out[0] is out[1] and out[0] == ("p", "q")


class Table:
    def __init__(self) -> None:
        self.rows: dict[tuple[int, int], int] = {}
        self.order: list[tuple[int, int]] = []

    def put(self, *args: int) -> int:
        if args in self.rows:
            return self.rows[args]
        n = len(self.rows)
        self.rows[args] = n
        self.order.append(args)
        return n

    def get(self, *args: int) -> int:
        return self.rows.get(args, -1) + len(args) + args[0]


def note(t: tuple[int, str]) -> None:
    saved.append(t)


def remember(*args):
    note(args)  # (another function keeps it)
    index[args] = len(index)
    seen.add(args)


def gives(*args):
    def inner():
        return args  # (a closure takes args: its tuple is made on the heap)

    return [inner()]


def lazy(*args):
    return (args[i] * 10 for i in range(len(args)))  # (a generator expression reads args later)


def lazy_over(*args):
    g = (x + 1 for x in args)
    return g


def counted(*args):
    n = 0
    for x in args:
        n += x
    a, b = args[0], args[-1]
    return n + len(args) + a * b + (1 if 3 in args else 0)


def text(*args):
    return f"{args} {len(args)} {'-'.join(args)} {args[1]}"


def through(*args):
    return store(*args), store(*args, 9)


def raising(*args):
    if len(args) > 1:
        raise ValueError(args)
    return args


@cache
def path(i: int, j: int) -> int:
    return 1 if i == 0 or j == 0 else path(i - 1, j) + path(i, j - 1)


lists = [stored("x", "y"), stored("z", "w")]
print(lists, lists[0][0] is lists[0][1])
print(aliased("p", "q"))
t = Table()
for i in range(6):
    print(t.put(i % 4, i % 2), end=" ")
print(t.rows, t.order, t.get(1, 1), t.get(5, 5))
for i in range(3):
    remember(i, "s" * (i + 1))
print(saved, index, sorted(seen), saved[0] in index)
print(gives("g", "h"), counted(1, 2, 3), counted(4, 5), text("a", "b", "c"), through(7, 8))
gens = [lazy(i, i + 1) for i in range(3)] + [lazy_over(i, 5 * i) for i in range(3)]
print([list(g) for g in gens])
r = [store(i, i + 1) for i in range(3)]
print(r, store(1) + store(2, 3), store())
try:
    raising(1, 2)
except ValueError as e:
    print("raised", e)
print(raising(5))
print(path(14, 14), path.cache_info())

# a tuple display that a lookup takes as its key is made in the frame too: a memo dict's hit
# allocates nothing, and its store makes the key it keeps
memo: dict[tuple[int, int], int] = {}


def grid(i: int, j: int) -> int:
    if (i, j) in memo:
        return memo[(i, j)]
    r = 1 if i == 0 or j == 0 else grid(i - 1, j) + grid(i, j - 1)
    memo[(i, j)] = r
    return r


print(grid(12, 12), len(memo), memo.get((3, 4), -1), memo.get((99, 1), -1), (2, 2) in memo, (50, 50) not in memo)
coords = {(1, "a"), (3, "b")}
print((1, "a") in coords, (3, "a") in coords, sorted(memo)[:3])
try:
    print(memo[(77, 78)])
except KeyError as e:
    print("KeyError", e)
