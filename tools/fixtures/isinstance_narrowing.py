"""Feature probe: does isinstance() narrow a base-typed value to a subclass?

Richards' task functions receive a base-typed record and read subclass fields after
`assert isinstance(d, DeviceTaskRec)`. Both forms must print `5 5` when narrowing works.
"""


class Base:
    def __init__(self) -> None:
        self.k = 0


class Child(Base):
    def __init__(self) -> None:
        super().__init__()
        self.extra = 5


def via_if(b: Base) -> int:
    if isinstance(b, Child):
        return b.extra
    return 0


def via_assert(b: Base) -> int:
    d = b
    assert isinstance(d, Child)
    return d.extra


print(via_if(Child()), via_assert(Child()))
