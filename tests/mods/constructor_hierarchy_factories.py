from mods.constructor_hierarchy import Invalid


def unused_helper(value: int) -> int:
    return Invalid([value]).score()


class Dormant:
    def __init__(self, value: int) -> None:
        self.value: int = unused_helper(value)


class Active:
    def __init__(self, value: int) -> None:
        self.value: int = value
