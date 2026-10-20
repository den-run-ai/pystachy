"""Mixed value operations dispatch once to the original native payload."""


def inspect(value: int | str | list[int] | list[str] | dict[str, int] | dict[int, str] | None) -> None:
    empty = ""
    print(bool(value), not value, str(value), repr(value), f"{value}", f"{value!r}", format(value, empty))
    print("yes" if value else "no")


def check() -> None:
    numbers = [1, 2]
    words = ["one", "two"]
    counts = {"first": 3}
    labels = {4: "four"}
    values: list[int | str | list[int] | list[str] | dict[str, int] | dict[int, str] | None] = [
        None, 0, 7, "", "a'\n\"\\é", numbers, words, counts, labels,
    ]
    for value in values:
        inspect(value)
    numbers.clear()
    words.clear()
    counts.clear()
    labels.clear()
    for value in values[5:]:
        inspect(value)
    print(values, {"saved": values[6]}, (values[5], values[6]))
    print(any(values), all(values))
    saved = values[5]
    if isinstance(saved, list):
        # Both list element types remain possible; truth/format need no cast.
        print(bool(saved), repr(saved))


def nested(value: int | str | list[int | str | None] | dict[str, int | list[str] | None] | None) -> None:
    print(bool(value), str(value), repr(value), f"{value}")


def only_box() -> int | list[str]:
    return ["kept-" + str(i) for i in range(3)]


def retained() -> None:
    value = only_box()
    for i in range(160):
        garbage = [str(i) * 30]
        garbage.clear()
    print(bool(value), str(value), repr(value))
    if isinstance(value, list):
        alias = value
        alias.append("changed")
        print(value is alias, repr(value))


check()
nested([1, "x", None])
nested({"count": 2, "names": ["A", "B"], "missing": None})
nested(None)
retained()
