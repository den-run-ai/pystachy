# error: expected listing, got list[int]
# (a class whose name starts with "list" is no list type)
class listing:
    def __init__(self, n: int) -> None:
        self.n = n


def collect(*args):
    out = []
    for a in args:
        out.append(a)
    return out


def use(x: listing) -> int:
    return x.n


print(use(collect()))
