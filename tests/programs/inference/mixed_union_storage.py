"""A union boxes the container reference, never copies or retypes its storage."""


class Holder:
    def __init__(self, value: int | str | list[int] | dict[str, int] | None) -> None:
        self.value: int | str | list[int] | dict[str, int] | None = value


def update(value: int | str | list[int] | dict[str, int] | None) -> int:
    if value is None:
        return -1
    if isinstance(value, list):
        value.append(9)
        return value[-1]
    if isinstance(value, dict):
        value["added"] = 7
        return value["added"]
    if isinstance(value, str):
        return len(value)
    return value + 1


def widen(value: int | list[int] | None) -> int | str | list[int] | dict[str, int] | None:
    return value


def optional_list(value: list[int] | None) -> int | list[int] | None:
    return value


def check() -> None:
    original = [1, 2]
    mapping = {"start": 3}
    values: list[int | str | list[int] | dict[str, int] | None] = [original, mapping, 2, "ok", None]
    saved = values[0]
    holder = Holder(values[1])
    for item in values:
        print(update(item))
    values[0] = "replaced"
    holder.value = 0
    # Keep the old container reachable only through its immutable union box.
    for i in range(150):
        values.append(str(i) * 40)
    if isinstance(saved, list):
        print(saved is original, saved)
        saved[0] = 8
    print(original, mapping)
    for item in [widen(4), widen(original), widen(None), optional_list(original), optional_list(None)]:
        print(update(item))


check()
