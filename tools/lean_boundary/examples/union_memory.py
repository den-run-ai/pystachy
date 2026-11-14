"""Closed-union reads of typed union memory: each write proved in its union, each read assuming it."""


class Reading:
    def __init__(self, value: int | str) -> None:
        self.value: int | str = value

    def scaled(self, factor: int | float = 2) -> float:
        if isinstance(factor, int):
            return self.size() * factor * 1.0
        return self.size() * factor

    def size(self) -> int:
        value = self.value
        if isinstance(value, int):
            return value
        return len(value)


latest: int | str = 0


def remember(value: int | str) -> None:
    global latest
    latest = value


def replaced(value: int | str) -> int:
    global latest
    latest = value
    current = latest
    if isinstance(current, int):
        return current
    return len(current)


def total(values: list[int | str]) -> int:
    count = 0
    for value in values:
        if isinstance(value, int):
            count += value
        else:
            count += len(value)
    return count


def pair(flag: bool) -> tuple[str, int | str]:
    return ("pair", 5 if flag else "five")


def unpacked(flag: bool) -> int:
    name, value = pair(flag)
    if isinstance(value, int):
        return value + len(name)
    return len(value) + len(name)


def noted(note=None, value: int | str = 0) -> int:
    # (a parameter of type None takes no operand: the call passes value first)
    if isinstance(value, int):
        return value
    return len(value)


def single(text: str, target: str | list[str]) -> bool:
    return len(text) > 0 and isinstance(target, str) and len(target) == 1 and target != "\\"


def measure() -> float:
    return Reading("abc").scaled() + Reading(4).scaled(0.5)


remember(3)
print(replaced(4), replaced("five"), total([1, "two", 3]), unpacked(True), unpacked(False))
print(single("x", "y"), single("x", ["y"]), single("", "y"), measure(), noted(None, 6), noted(None, "seven"))
