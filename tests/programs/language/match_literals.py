events: list[str] = []


def source(value: int) -> int:
    events.append("subject")
    return value


def guarded(value: int) -> bool:
    events.append("guard:" + str(value))
    return value < 0


def classify(value: int) -> str:
    match source(value):
        case 0:
            return "zero"
        case 1 | 2:
            return "small"
        case held if guarded(held):
            return "negative"
        case _:
            return "other:" + str(held)


for value in [-1, 0, 1, 2, 8]:
    events.clear()
    print(classify(value), events)


def singleton(value):
    match value:
        case True:
            return "true"
        case False:
            return "false"
        case None:
            return "none"
        case 1:
            return "one"
        case -2.5:
            return "fraction"
        case "snow":
            return "text"
        case b"ice":
            return "bytes"
        case _:
            return "other"


print(singleton(True), singleton(False), singleton(None))
print(singleton(1), singleton(1.0), singleton(-2.5))
print(singleton("snow"), singleton(b"ice"), singleton(3))


class NoTruth:
    def __bool__(self) -> bool:
        raise ValueError("capture must not ask for truth")


def capture(value: NoTruth) -> bool:
    match value:
        case held:
            return held is value


print(capture(NoTruth()))
