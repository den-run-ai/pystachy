# len() of *args (a tuple) or **kwargs (a record) is a constant where the argument types are
# known, so a template can dispatch on how many arguments it got: only the branch that runs is
# compiled (args[0] where there are none would not compile)
def first_or(default, *args):
    if len(args) == 0:
        return default
    return args[0]


def describe(*args, **kwargs):
    if len(args) == 2 and len(kwargs) == 0:
        return f"pair {args[0]} {args[1]}"
    if 1 <= len(args) and len(kwargs) > 0:
        return f"{len(args)} and {sorted(kwargs)}"
    if len(args) != 1:
        return "many"
    return "one " + str(args[0])


class M:
    def __init__(self, n: int) -> None:
        self.n = n

    def one(self, g):
        if isinstance(g, str):
            return "name:" + g
        return "idx:" + str(g + self.n)

    def group(self, *args):
        if len(args) == 0:
            return self.one(0)
        if len(args) == 1:
            return self.one(args[0])
        if len(args) == 2:
            return (self.one(args[0]), self.one(args[1]))
        return (self.one(args[0]), self.one(args[1]), self.one(args[2]))


print(first_or(5), first_or(5, "x"), first_or("d", 1, 2))
print(describe(1, 2), describe(1, k=2), describe(1, 2, 3), describe(7), describe())
m = M(1)
print(m.group(), m.group(2), m.group("x"), m.group(1, "y"), m.group(0, 1, 2))
t = (1, 2, 3)
print("three" if len(t) == 3 else t[5], len(t) > 2, [x for x in t if len(t) >= 3])


def maybe(flag: bool) -> str:
    # (folding the test keeps the read of u, which raises where u is unbound)
    if flag:
        u = (1, 2)
    try:
        return "two" if len(u) == 2 else "other"
    except UnboundLocalError as e:
        return "unbound: " + str(e)


print(maybe(True), maybe(False))
