# A module that opts in to dynamic Any and names no type[C]: its classes are class boxes where
# the program does not compile with typed class objects (the list of classes that a builtin
# class joins), whatever the modules that import it annotate
# (tests/programs/inference/dynany_class_boxes_module.py)
# pystachy: dynamic-any
from typing import Any


class Plugin:
    def __init__(self, name: str = "p") -> None:
        self.name = name


class Loud(Plugin):
    pass


kinds = [Plugin, Loud]
kinds.append(str)


def names() -> list[str]:
    return [k.__name__ for k in kinds]


def holds(k: Any) -> bool:
    return k in kinds
