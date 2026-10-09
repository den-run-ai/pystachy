# d.setdefault(k, []).append(v) and d.setdefault(k, {})[k2] = v show what an empty d holds,
# also to a read before them; and a function whose first fill of an empty global shows nothing
# (REG[k] = []) is not what types it, when another function's fill does.
def group(xs: list[int]) -> None:
    d = {}
    for x in xs:
        if x % 3 in d:
            print("again", x % 3)
        d.setdefault(x % 3, []).append(x)
    print(d)


group([1, 2, 4, 5, 7])


def nest(xs: list[str]) -> None:
    d = {}
    for x in xs:
        if x[0] in d:
            print("seen", x[0])
        d.setdefault(x[0], {})[x] = len(x)
    print(d)


nest(["ab", "ac", "b"])
REG = {}


def add(k: str, v: int) -> None:
    if k not in REG:
        REG[k] = []
    REG[k].append(v)


def init(k: str) -> None:
    REG[k] = [0]


print(REG)
init("z")
add("a", 1)
add("a", 2)
print(REG)
