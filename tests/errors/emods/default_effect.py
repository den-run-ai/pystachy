def note(s: str) -> int:
    print("note:", s)
    return 1


def apply(x, f=(note("default"), lambda v: v)):
    return x
