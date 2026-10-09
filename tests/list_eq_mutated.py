# == and ordering of lists whose items' __eq__ changes the lists being compared: as in CPython's
# list_richcompare, both lengths are re-read at every step, and the lengths decide once a list
# has no item left (no read of a vacated or missing slot)
class E:
    def __init__(self, v: int, act: str):
        self.v = v
        self.act = act

    def __eq__(self, o: "E") -> bool:
        print("  eq", self.v, o.v, len(xs), len(ys))
        a = self.act
        self.act = ""
        if a == "clear ys":
            ys.clear()
        elif a == "clear both":
            xs.clear()
            ys.clear()
            return False
        elif a == "pop ys":
            ys.pop()
        elif a == "grow xs":
            for i in range(6):
                xs.append(E(100 + i, ""))
        elif a == "grow ys":
            for i in range(6):
                ys.append(E(100 + i, ""))
        elif a == "grow both":
            xs.append(E(5, ""))
            ys.append(E(5, ""))
        elif a == "replace":
            ys[0] = E(0, "")
            return False
        elif a == "outer":
            yy.clear()
        return self.v == o.v

    def __lt__(self, o: "E") -> bool:
        print("  lt", self.v, o.v, len(xs), len(ys))
        return self.v < o.v

    def __le__(self, o: "E") -> bool:
        print("  le", self.v, o.v, len(xs), len(ys))
        return self.v <= o.v

    def __gt__(self, o: "E") -> bool:
        print("  gt", self.v, o.v, len(xs), len(ys))
        return self.v > o.v

    def __ge__(self, o: "E") -> bool:
        print("  ge", self.v, o.v, len(xs), len(ys))
        return self.v >= o.v

    def __repr__(self) -> str:
        return f"E{self.v}"


xs: list[E] = []
ys: list[E] = []


def fill(n: int, act: str) -> None:
    xs.clear()
    ys.clear()
    for i in range(n):
        xs.append(E(i + 1, act if i == 0 else ""))
        ys.append(E(i + 1, ""))


for act in ["", "clear ys", "clear both", "pop ys", "grow xs", "grow ys", "grow both"]:
    fill(3, act)
    print(repr(act), "==")
    print(xs == ys, xs, ys)
    fill(3, act)
    print(repr(act), "!=")
    print(xs != ys)

for op in ["<", "<=", ">", ">="]:
    for act in ["clear ys", "clear both", "pop ys", "grow xs", "grow ys", "replace"]:
        fill(2, act)
        print(repr(act), op)
        if op == "<":
            print(xs < ys, xs, ys)
        elif op == "<=":
            print(xs <= ys, xs, ys)
        elif op == ">":
            print(xs > ys, xs, ys)
        else:
            print(xs >= ys, xs, ys)

# lists of lists: an inner __eq__ empties the outer list being compared
xx: list[list[E]] = [[E(1, "outer")], [E(2, "")]]
yy: list[list[E]] = [[E(1, "")], [E(2, "")]]
print("nested", xx == yy, len(xx), len(yy))
xx = [[E(1, "outer")], [E(2, "")]]
yy = [[E(1, "")], [E(2, "")]]
print("nested <", xx < yy, xx > yy)

# a tuple holding the lists
fill(2, "clear ys")
t1 = (xs, 1)
t2 = (ys, 1)
print("tuple", t1 == t2, t1 < t2)
