"""The ordinary base of tests/hiermods/futs.py's generic classes."""


class Base:
    def __init__(self, name: str) -> None:
        self.name = name

    def kind(self) -> str:
        return "base " + self.name
