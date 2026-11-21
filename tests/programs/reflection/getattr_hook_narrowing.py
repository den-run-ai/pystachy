# __getattr__ (#1536) and the narrowing of attribute paths: a test of o.f narrows the reads of
# o.f that follow it while nothing can have changed the field. A read that may call the method
# (of a field it answers while unassigned) is a call: it narrows nothing, and it voids what the
# tests of other attributes narrowed.
class Box:
    def __init__(self, full: bool) -> None:
        self.calls = 0
        self.other: int | None = 1
        if full:
            self.value: int | None = 5

    def __getattr__(self, name: str) -> int | None:
        self.calls += 1
        if name == "value":
            self.other = None
            return 7 if self.calls == 1 else None
        return None


def reread() -> None:
    # each read of the unassigned field asks the method again
    b = Box(False)
    if b.value is not None:
        print("value", b.value)
    print(b.calls)


def voided() -> None:
    # the method assigns other, which the test narrowed
    c = Box(False)
    if c.other is not None:
        v = c.value
        w = c.other
        print(v, w)


def kept() -> None:
    # a field that __init__ always assigns is narrowed as in a class without the method
    d = Box(True)
    if d.other is not None:
        print(d.other + 1, d.value, d.calls)


reread()
voided()
kept()
