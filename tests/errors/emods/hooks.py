def setup() -> None:
    pass


class Hooks:
    def __init__(self) -> None:
        self.ready = setup()
        self.n = 1


def count() -> int:
    return 2
