# Objects of dict subclasses under collection: an object begins with its dict's header (the
# pointers to its key, value, hash and index arrays), and its own fields follow, so the collector
# must keep the arrays, the keys and values in them and the fields alive through the one pointer,
# and growth (a new table) must never write over the fields.


class Leaf:
    def __init__(self, name: str) -> None:
        self.name = name
        self.parts: list[str] = [name + ".a", name + ".b"]


class Index(dict[str, Leaf]):
    def __init__(self, tag: str) -> None:
        super().__init__()
        self.tag = tag
        self.order: list[str] = []
        self.owner = Leaf(tag)

    def add(self, key: str) -> None:
        self[key] = Leaf(self.tag + "/" + key)
        self.order.append(key)

    def check(self) -> bool:
        if self.owner.name != self.tag or self.owner.parts[1] != self.tag + ".b":
            return False
        if list(self) != self.order:
            return False
        for k, v in self.items():
            if v.name != self.tag + "/" + k or v.parts != [v.name + ".a", v.name + ".b"]:
                return False
        return True


class Memo(dict[str, str]):
    # (no fields of its own: only the header's words keep the tables, and the strs in them, alive)
    def __missing__(self, key: str) -> str:
        v = key.upper() + "!"
        self[key] = v
        return v


def churn(n: int) -> int:
    junk = 0
    for i in range(n):
        junk += len({str(i): [str(i + 1)], "x" * (i % 5): []})
    return junk


idx: list[Index] = []
for n in range(30):
    x = Index("i" + str(n))
    for i in range(n % 11):
        x.add("k" + str(i))
        churn(3)
    idx.append(x)
    churn(20)
print(all([x.check() for x in idx]), sum(len(x) for x in idx), idx[10]["k3"].name)

# grow past several tables, delete, and grow again
for n in range(0, 30, 6):
    x = idx[n]
    for i in range(len(x), 40):
        x.add("k" + str(i))
    churn(100)
    ok = x.check()
    for i in range(0, 40, 2):
        del x["k" + str(i)]
        x.order.remove("k" + str(i))
    churn(100)
    ok = ok and x.check() and len(x) == 20
    x.add("again")
    churn(50)
    print(n, ok and x.check(), len(x), x["k39"].parts[0], x.owner.name)

memos: list[Memo] = []
for n in range(50):
    m = Memo()
    for i in range(n % 6 + 1):
        print(m["w" + str(n) + "." + str(i)], end=" " if n % 10 == 9 and i == 0 else "")
        churn(5)
    memos.append(m)
print()
churn(3000)
print(len(memos), sorted(memos[49].items()), memos[13]["w13.0"], sum(len(m) for m in memos), all(m["w" + str(n) + ".0"] == ("w" + str(n) + ".0").upper() + "!" for n, m in enumerate(memos)))
