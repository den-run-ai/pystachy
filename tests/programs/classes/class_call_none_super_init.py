class Base:
    def __init__(self) -> None:
        print("base init")


class Child(Base):
    def initialize(self) -> None:
        super().__init__()
        print("initialized")

    def explicit(self) -> None:
        super(Child, self).__init__()
        print("explicit")

    def reassign(self) -> None:
        self = None
        super().__init__()
        print("reassigned")


def absent() -> Child | None:
    return None


Child.initialize(absent())
Child.explicit(absent())
child = Child()
Child.initialize(child)
Child.explicit(child)
child.reassign()
