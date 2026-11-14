from typing import Final


class Node:
    KINDS: Final = ("leaf", "branch")

    def describe(self) -> str:
        return "/".join(self.KINDS)


class Sub(Node):
    TABLE: Final = {"x": [1, 2], "y": []}


class Unused:
    KEYS: Final = {1, 2}  # (a set's type is not inferred: an error only where the class is used)
