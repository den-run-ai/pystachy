# a class whose field holds the None a function returns (none_field_import)
def setup() -> None:
    pass


class Hooks:
    def __init__(self) -> None:
        self.ready = setup()
        self.n = 1


def count() -> int:
    return 2
