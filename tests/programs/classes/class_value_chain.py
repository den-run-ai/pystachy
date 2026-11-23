# Each receiver runs once, before the next constructor's arguments.
events: list[int] = []


def arg(value: int) -> int:
    events.append(-value)
    return value


class Base:
    def __init__(self, value: int) -> None:
        events.append(value)
        self.value = value


class Child(Base):
    pass


def start() -> Base:
    return Child(arg(1))


value = start().__class__(arg(2)).__class__(arg(3)).__class__(arg(4))
print(type(value).__name__, value.value, events)
