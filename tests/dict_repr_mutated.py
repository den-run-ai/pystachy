# dict == whose values' __eq__ changes the dicts, and repr of lists and dicts whose items'
# __repr__ changes them: like CPython (dict_equal, list_repr, dict_repr), every step reads the
# current entries, and the length checked at the start of dict == is not checked again
class V:
    def __init__(self, v: int, act: str):
        self.v = v
        self.act = act

    def run(self) -> None:
        a = self.act
        self.act = ""
        if a == "clear d1":
            d1.clear()
        elif a == "clear d2":
            d2.clear()
        elif a == "del b":
            del d1["b"]
            if "b" in d2:
                del d2["b"]
        elif a == "regrow":
            del d1["a"]
            for k in ["c", "d", "e", "f", "g"]:
                d1[k] = V(3, "")
        elif a == "add":
            d1["z"] = V(26, "")
        elif a == "clear rs":
            rs.clear()
        elif a == "grow rs":
            rs.append(V(8, ""))
        elif a == "clear nest":
            nest.clear()

    def __eq__(self, o: "V") -> bool:
        print("  eq", self.v, o.v, len(d1), len(d2))
        self.run()
        return self.v == o.v

    def __repr__(self) -> str:
        self.run()
        return f"V{self.v}"


d1: dict[str, V] = {}
d2: dict[str, V] = {}


def fill(act: str, k2: str) -> None:
    d1.clear()
    d2.clear()
    d1["a"] = V(1, act)
    d1["b"] = V(2, "")
    d2["a"] = V(1, "")
    d2[k2] = V(2 if k2 == "b" else 3, "")


for act in ["", "clear d2", "clear d1", "del b", "add"]:
    fill(act, "b")
    print(repr(act), d1 == d2, len(d1), len(d2))
    fill(act, "b")
    print(repr(act), d1 != d2, len(d1), len(d2))
fill("regrow", "c")
print("regrow", d1 == d2, list(d1), list(d2))

rs: list[V] = [V(1, "clear rs"), V(2, "")]
print(rs, len(rs))
rs = [V(1, "grow rs"), V(2, "")]
print(rs, len(rs))
rs = [V(1, ""), V(2, "grow rs"), V(3, "clear rs")]
print(f"{rs}", len(rs))
nest: list[list[V]] = [[V(1, "clear nest"), V(2, "")], [V(3, "")]]
print(nest, len(nest))

fill("del b", "b")
d1["c"] = V(3, "")
print(d1)
fill("clear d1", "b")
print(d1)
fill("add", "b")
print(str(d1), d1)
dl: dict[str, list[V]] = {"x": [V(1, "clear rs")], "y": []}
rs = [V(5, "")]
print(dl, rs)
