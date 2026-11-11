# mypy/types.py has unions wider than four, e.g. ProperType alternatives and `Type | str | None` style members
class A:
    def n(self) -> int: return 1
class B:
    def n(self) -> int: return 2
class C:
    def n(self) -> int: return 3
class D:
    def n(self) -> int: return 4
class E:
    def n(self) -> int: return 5
def total(xs: list[A | B | C | D | E]) -> int:
    return sum([x.n() for x in xs])
print(total([A(), B(), C(), D(), E()]))
