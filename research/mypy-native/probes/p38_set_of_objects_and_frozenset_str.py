class Var:
    def __init__(self, n: str) -> None:
        self.n = n
seen: set[Var] = set()
v = Var("a")
seen.add(v)
seen.add(v)
names: frozenset[str] = frozenset({"x", "y"})
print(len(seen), v in seen, "x" in names)
