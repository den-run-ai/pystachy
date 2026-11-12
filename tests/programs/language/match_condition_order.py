class Probe:
    def __init__(self, number: int, seen: list[str]) -> None:
        self.number = number
        self.seen = seen

    def __eq__(self, other: int) -> bool:
        self.seen.append("eq:" + str(other))
        return self.number == other


class Guard:
    def __init__(self, label: str, answer: bool, seen: list[str]) -> None:
        self.label = label
        self.answer = answer
        self.seen = seen

    def __bool__(self) -> bool:
        self.seen.append(self.label)
        return self.answer


def choose(number: int) -> None:
    seen: list[str] = []
    saved = 99
    match (Probe(number, seen), 7):
        case (1, saved) if Guard("false:" + str(saved), False, seen):
            print("unreachable")
        case (2, saved) if (Guard("left", True, seen) and Guard("middle", False, seen)) or Guard("right", True, seen):
            seen.append("body:" + str(saved))
        case _:
            seen.append("fallback:" + str(saved))
    print(number, saved, seen)


def alternatives(number: int) -> None:
    seen: list[str] = []
    saved = 99
    match (7, Probe(number, seen)):
        case (saved, 1) | (saved, 2) if Guard("guard:" + str(saved), True, seen):
            seen.append("body:" + str(saved))
        case _:
            seen.append("fallback:" + str(saved))
    print(number, saved, seen)


for value in [1, 2, 3]:
    choose(value)
    alternatives(value)


def classify(value: int | str) -> str:
    captured: int | str = "old"
    match value:
        case captured if isinstance(captured, int):
            return "int"
        case _:
            return "other"


print(classify(1), classify("s"))
