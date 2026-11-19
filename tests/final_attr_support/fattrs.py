from typing import Final


class Node:
    KINDS: Final = ("leaf", "branch")

    def describe(self) -> str:
        return "/".join(self.KINDS)


class Sub(Node):
    TABLE: Final = {"x": [1, 2], "y": []}


class Unused:
    KEYS: Final = {1, "a"}  # (a set of mixed items has no type: an error only where the class is used)
