events: list[str] = []


class C:
    pass


def source() -> int:
    events.append("source")
    return 1


c = C()
original = c
try:
    c += source()
except TypeError as error:
    print(error)
print(c is original, events)
