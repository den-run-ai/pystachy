"""A class of a module with the container protocol, and one Pystachy cannot iterate, unused."""
from collections.abc import Iterator


class Table:
    def __init__(self) -> None:
        self.rows: dict[str, list[str]] = {}

    def __getitem__(self, name: str) -> list[str]:
        return self.rows[name]

    def __setitem__(self, name: str, row: list[str]) -> None:
        self.rows[name] = row

    def __contains__(self, name: str) -> bool:
        return name in self.rows

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self.rows))


class Lines:
    def __init__(self, text: str) -> None:
        self.text = text

    def __iter__(self) -> Iterator[str]:
        for line in self.text.splitlines():
            yield line
