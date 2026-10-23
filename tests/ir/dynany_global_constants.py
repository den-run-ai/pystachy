# pystachy: dynamic-any
# Constants and scalar arithmetic cannot allocate. A mutable-global copy snapshots.
SMALL = 17
LARGE = 1000
MUTABLE = 19


def constants() -> int:
    return SMALL + LARGE


def mutable() -> int:
    global MUTABLE
    value = MUTABLE
    MUTABLE += 1
    return value
