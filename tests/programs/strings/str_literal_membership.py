def matches(value: str | None) -> None:
    print(value in ["{", "[", None], value not in ["{", "[", None])
    print(value in ["", "é", "🌲", "two", "two"], value not in ["", "é", "🌲", "two", "two"])


for value in ["{", "[", "}", "", "é", "🌲", "two", "t", None]:
    matches(value)


def needle(events: list[str], value: str | None) -> str | None:
    events.append("needle")
    return value


events: list[str] = []
print(needle(events, "a") in ["a", None, "b"], events)
events.clear()
print(needle(events, None) not in ["a", None, "b"], events)


def item(events: list[str], value: str) -> str:
    events.append(value)
    return value


# Nonliteral items keep the ordinary list path and evaluate every item before
# searching, even when the first one matches.
events.clear()
print(needle(events, "a") in [item(events, "a"), item(events, "b")], events)
items = ["a", "b"]
print("b" in [*items, "c"], "z" not in [*items, "c"])
print("i" in ["a", "b", "c", "d", "e", "f", "g", "h", "i"])
print("a" in ["a"] == ["a"])
