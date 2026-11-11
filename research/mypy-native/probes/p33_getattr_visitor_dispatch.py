# reflective dispatch: getattr(self, "visit_" + name) (59 getattr calls; mypy/traverser, stubgen, strconv)
class V:
    def visit_a(self) -> str:
        return "A"
    def visit_b(self) -> str:
        return "B"
    def go(self, name: str) -> str:
        return getattr(self, "visit_" + name)()
print(V().go("a"), V().go("b"))
