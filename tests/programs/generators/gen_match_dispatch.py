from collections.abc import Iterator


events: list[str] = []


def source(value: tuple[int, str]) -> tuple[int, str]:
    events.append("subject")
    return value


def select(values: list[tuple[int, str]]) -> Iterator[str]:
    try:
        for value in values:
            match source(value):
                case (0, _):
                    continue
                case (1 | 2, text) if len(text) > 0:
                    yield text
                case (kind, text):
                    yield str(kind) + ":" + text
    finally:
        events.append("closed")


print(list(select([(0, "skip"), (1, "one"), (2, ""), (3, "other")])))
print(events)
events.clear()
generator = select([(1, "held"), (2, "unused")])
print(next(generator), events)
generator.close()
print(events)
