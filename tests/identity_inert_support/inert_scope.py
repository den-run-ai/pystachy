# pystachy: identity-inert
"""Checked hint exercised independently from the JSON library."""
type Value = None | bool | int | str | list[Value] | dict[str, Value]


class Cursor:
    def __init__(self, text: str) -> None:
        self.pos = len(text)

    def step(self, text: str) -> str:
        i = self.pos
        i += len(text)
        self.pos = i
        return str(i)


def make(text: str) -> Cursor:
    return Cursor(text)


def decode(text: str) -> Value:
    n = int(text)
    return {"value": n, "again": n, "nested": [n, text]}


def observes() -> bool:
    value = float("nan")
    items = [value]
    return value in items and items == [value]
