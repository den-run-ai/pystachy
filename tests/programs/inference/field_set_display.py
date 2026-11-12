# Fields typed by set displays in __init__: a set of the first item's type, one per object.
class Scope:
    def __init__(self, first: int, name: str) -> None:
        self.ids = {first}
        self.names = {name, "self"}
        self.keys = {("a", 1), ("b", 2)}
        self.codes = {b"x", b"y"}
        self.by_kind = {"kw": {"if", "else"}}
        self.rows = [{1, 2}]
        self.pair = ({"p"}, 0)


a = Scope(7, "n")
b = Scope(8, "m")
a.ids.add(9)
a.names.discard("self")
a.by_kind["kw"].add("while")
a.rows[0].add(3)
a.pair[0].add("q")
print(sorted(a.ids), sorted(a.names), sorted(a.keys), sorted(a.codes))
print(sorted(a.by_kind["kw"]), sorted(a.rows[0]), sorted(a.pair[0]), a.pair[1])
print(sorted(b.ids), sorted(b.names), sorted(b.by_kind["kw"]), sorted(b.rows[0]), sorted(b.pair[0]))
print(("a", 1) in a.keys, ("a", 2) in a.keys, b"x" in b.codes, a.ids is b.ids)
a.ids = {1}
print(sorted(a.ids), sorted(b.ids))
