# pystachy: dynamic-any
# Reads of proven integer constants cannot allocate. A mutable global still snapshots.
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
