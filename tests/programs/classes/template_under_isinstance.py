# isinstance() of a value of an ordinary class and class templates under it (#962), compiled in
# count_t() at its first call, before the program makes its first T or S: each test holds for every
# specialization that code makes later, and the value keeps its class (the filtered lists hold
# Base objects).
class Base:
    def __init__(self) -> None:
        self.w = 1

    def weight(self) -> int:
        return self.w


class T(Base):
    def __init__(self, item, scale=2):
        super().__init__()
        self.item = item
        self.scale = scale

    def weight(self) -> int:
        return self.w * self.scale + len(str(self.item))


class S(Base):
    def __init__(self, a, b):
        super().__init__()
        self.a = a
        self.b = b

    def weight(self) -> int:
        return 100


def total(xs):
    n = 0
    for x in xs:
        n += x.weight()
    return n


def count_t(xs: list[Base]) -> int:
    ts = [x for x in xs if isinstance(x, T)]
    return len(ts) * 10 + len([x for x in xs if isinstance(x, S)]) + total(ts) * 0


def main() -> None:
    items: list[Base] = [Base()]
    print(total(items), count_t(items))
    items.append(T("abc"))
    print(total(items), count_t(items))
    items.append(T(12345, 3))
    items.append(S(1, "x"))
    items.append(S(2.5, None))
    print(total(items), count_t(items))
    for x in [T(b"zz", 5), T((1, 2))]:
        items.append(x)
    print(total(items), count_t(items), [isinstance(x, T) for x in items])


main()
