# An empty list read before the code that fills it takes the type of its first fill, and a test
# that the argument types decide leads only into the branch that runs there. A parameter whose
# argument is None is None up to the statement that gives it a value (if x is None: x = 3), and
# a fill in a branch that its test leaves out, before or after the read, does not count.
class N:
    def __init__(self, v: int) -> None:
        self.v = v


def find(items: list[int], k: int) -> N | None:
    for i in items:
        if i == k:
            return N(i)
    return None


def before(x):
    xs = []
    print(sum(xs))
    if x is not None:
        xs.append(0.5)
    if x is None:
        x = 3
    return x


def other_branch(x):
    xs = []
    print(xs)
    if x is not None:
        xs.append(1)
    else:
        xs.append("s")
    x = 5
    print(xs, x)


def read_after(x):
    xs = []
    if x is not None:
        xs.append(0.5)
    else:
        pass
    x = 3
    print(sum(xs))
    xs.append(x)
    return xs


def varargs(x, *args):
    xs = []
    print(xs)
    for a in args:
        xs.append("s")
    if x is None:
        xs.append(1)
    return xs


def by_value(x, items):
    out = []
    if len(items) == 0:
        return out
    for it in items:
        m = find(items, it)
        if m is not None:
            out.append(x)
    return out


print(before(None))
other_branch(None)
print(read_after(None))
print(varargs(None))
print(by_value(1, [1, 2]))
nothing: list[int] = []
print(by_value(1, nothing))
