# Empty containers that only importers fill (REG, ITEMS, ALIASED), and one that only a
# function of this module fills (NAMES); dump() reads them after the importers have.
REG = {}
ITEMS = []
NAMES = {}
ALIASED = {}


def name(k: str, v: int) -> None:
    NAMES.setdefault(k, []).append(v)


def dump() -> None:
    print("reg:", REG, ITEMS, NAMES, ALIASED)
