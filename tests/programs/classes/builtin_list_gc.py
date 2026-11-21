# Objects of list subclasses under collection: an object begins with its list's header, and its
# own fields follow, so the collector must keep the item array, the items and the fields alive
# through the one pointer, and growth must never write items over the fields. Every object here
# holds references in its fields and in its items while the loops allocate.


class Node:
    def __init__(self, label: str) -> None:
        self.label = label
        self.kids: list[str] = [label + "!", label + "?"]


class Bag(list):
    def __init__(self, tag: str) -> None:
        super().__init__()
        self.tag = tag
        self.notes: list[str] = [tag + "-note"]
        self.owner = Node(tag)

    def check(self, n: int) -> bool:
        if self.tag != "bag" + str(n) or self.notes[0] != self.tag + "-note" or self.owner.label != self.tag:
            return False
        if self.owner.kids != [self.tag + "!", self.tag + "?"]:
            return False
        for i, item in enumerate(self):
            if item.label != "{}/{}".format(self.tag, i) or item.kids[1] != item.label + "?":
                return False
        return True


class Counts(list[int]):
    def __init__(self, name: str) -> None:
        self.name = name
        self.seen: dict[str, int] = {}


class Words(list[str]):
    # (no fields of its own: only the header's words keep the item array, and the strs in it,
    # alive; were the object's memory not scanned, the collector would free them)
    def joined(self) -> str:
        return "/".join(self)


def churn(n: int) -> int:
    junk = 0
    for i in range(n):
        junk += len([str(i), str(i + 1), "x" * (i % 7)])
    return junk


bags: list[Bag] = []
for n in range(40):
    b = Bag("bag" + str(n))
    for i in range(n % 9):
        b.append(Node("{}/{}".format(b.tag, i)))
        churn(3)
    bags.append(b)
    churn(20)
print(all([bags[n].check(n) for n in range(len(bags))]), sum(len(b) for b in bags))

# grow past the header's first array, shrink to empty, and grow again
for n in range(0, 40, 7):
    b = bags[n]
    for i in range(len(b), 30):
        b.append(Node("{}/{}".format(b.tag, i)))
    churn(50)
    ok = b.check(n)
    while len(b) > 0:
        b.pop()
    churn(50)
    ok = ok and b.check(n) and len(b) == 0 and b.notes == [b.tag + "-note"]
    for i in range(3):
        b.append(Node("{}/{}".format(b.tag, i)))
    b.insert(0, Node("first"))
    del b[0]
    b.extend([Node("{}/{}".format(b.tag, 3)), Node("{}/{}".format(b.tag, 4))])
    churn(50)
    print(n, ok and b.check(n), len(b), b[4].label, b.owner.kids[0], b.notes)

cs: list[Counts] = []
for n in range(30):
    c = Counts("c" + str(n))
    for i in range(n):
        c.append(i * n)
        c.seen[str(i)] = i
    churn(15)
    cs.append(c)
churn(2000)
print([sum(c) for c in cs][-3:], [len(c.seen) for c in cs][-3:], cs[29].name, cs[29][28], cs[5] == [0, 5, 10, 15, 20])
kept = [c for c in cs if len(c) % 2 == 1]
cs = []
churn(2000)
print(len(kept), kept[-1].name, kept[-1][-1], kept[-1].seen["28"], kept[3][1:4], sorted(kept[2], reverse=True)[:2])

ws: list[Words] = []
for n in range(60):
    w = Words()
    for i in range(n % 7 + 1):
        w.append("w" + str(n) + "." + str(i))
    churn(10)
    ws.append(w)
churn(3000)
print(len(ws), ws[59].joined(), ws[13].joined(), sum(len(w) for w in ws), all(w[0] == "w" + str(n) + ".0" for n, w in enumerate(ws)))
