# For tests/errors/inference/dynany_declines_*.py: Bag's and Ver's comparison methods do not
# compile for an Any operand (each compares a typed list with an Any value's field), so a module
# that boxes their objects into Any declines them; Bag.bad, Other.bad and broken do not compile,
# and an imported module's functions are compiled where they are called, after those methods
class Bag:
    def __init__(self, n: int) -> None:
        self.items = [n]

    def __eq__(self, other):
        return self.items == other.items

    def bad(self) -> int:
        return eval("1")


class Ver:
    def __init__(self, n: int) -> None:
        self.parts = [n]

    def __lt__(self, other):
        return self.parts < other.parts


class Other:
    def bad(self) -> int:
        return eval("2")


def broken() -> int:
    return eval("3")
