# int() with an explicit base of a str | None that is None raises CPython's error for a base


def get(c: bool) -> str | None:
    return "17" if c else None


print(int(get(True), 10))
print(int(get(False), 10))
