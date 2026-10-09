# in, index, count, remove, min and max over a list that the items' __eq__/__lt__/__gt__ change:
# like CPython, the length is re-read at every step, remove deletes the slot __eq__ answered for
# (nothing once the list no longer has it), and min/max keep the item they compared
class S:
    def __init__(self, v: int, act: str):
        self.v = v
        self.act = act

    def run(self) -> None:
        a = self.act
        self.act = ""
        if a == "clear":
            xs.clear()
        elif a == "pop0":
            xs.pop(0)
        elif a == "ins0":
            xs.insert(0, S(9, ""))
        elif a == "grow":
            xs.append(S(1, ""))
            xs.append(S(2, ""))
        elif a == "clear ll":
            ll.clear()

    def __eq__(self, o: "S") -> bool:
        print("  eq", self.v, o.v, len(xs))
        self.run()
        return self.v == o.v

    def __lt__(self, o: "S") -> bool:
        print("  lt", self.v, o.v, len(xs))
        self.run()
        return self.v < o.v

    def __gt__(self, o: "S") -> bool:
        print("  gt", self.v, o.v, len(xs))
        self.run()
        return self.v > o.v

    def __repr__(self) -> str:
        return f"S{self.v}"


xs: list[S] = []


def fill(acts: list[str]) -> None:
    xs.clear()
    for i in range(len(acts)):
        xs.append(S(i + 1, acts[i]))


fill(["clear", "", ""])
print("in", S(2, "") in xs, xs)
fill(["", "ins0", "", ""])
print("in", S(3, "") in xs, xs)
fill(["", "pop0", "", ""])
print("not in", S(3, "") not in xs, xs)
fill(["", "ins0", "", ""])
print("index", xs.index(S(3, "")), xs)
fill(["", "pop0", "", ""])
print("index", xs.index(S(4, ""), 1, 3), xs)
fill(["grow", "", "", ""])
print("count", xs.count(S(1, "")), xs)
fill(["", "clear", ""])
print("count", xs.count(S(2, "")), xs)

# remove deletes the slot where __eq__ said yes, whatever is there now
fill(["", "pop0", ""])
xs.remove(S(2, ""))
print("remove", xs)
fill(["", "pop0"])
xs.remove(S(2, ""))
print("remove", xs)
fill(["", "clear"])
xs.remove(S(2, ""))
print("remove", xs)
fill(["", "ins0", ""])
xs.remove(S(2, ""))
print("remove", xs)

# min and max keep the item they compared, though __lt__ or __gt__ moved or dropped it
fill(["", "clear", ""])
xs[0].v = 5
print("min", min(xs), xs)
fill(["", "ins0", ""])
xs[1].v = 7
print("max", max(xs), xs)
fill(["", "grow", ""])
print("max", max(xs), xs)
fill(["", "pop0", "", ""])
xs[0].v = 9
print("min", min(xs), xs)

# a list of lists that an item's __eq__ empties while it is searched
ll: list[list[S]] = [[S(1, "clear ll")], [S(2, "")]]
print("lists", [S(2, "")] in ll, ll)
ll = [[S(1, "")], [S(2, "clear ll")], [S(2, "")]]
print("lists", ll.count([S(2, "")]), ll)
