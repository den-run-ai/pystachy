def make(n: int) -> list[str]:
    out: list[str] = []
    for i in range(n):
        out.append(str(i) * 3)
    return out


def total(xs: list[str]) -> int:
    t = 0
    for x in xs:
        t += len(x)
    return t


def lookup(n: int) -> int:
    d: dict[str, int] = {"k1": 1}
    try:
        return d["k" + str(n)]
    except KeyError:
        return -1


def boom(n: int) -> int:
    d: dict[str, int] = {"k1": 1}
    return d["k" + str(n)]


COUNT = 7
print("module init ran")
