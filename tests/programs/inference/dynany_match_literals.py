# pystachy: dynamic-any
from dataclasses import dataclass
from typing import Any


def classify(value: Any) -> str:
    match value:
        case True:
            return "true"
        case False:
            return "false"
        case None:
            return "none"
        case 1:
            return "one"
        case "text":
            return "text"
        case captured:
            return str(captured)


print(classify(True), classify(False), classify(None), classify(1), classify("text"), classify(7))


@dataclass
class Box:
    value: int


@dataclass
class Other:
    value: int


def concrete_mismatch(value: Other) -> int:
    match value:
        case Box(item):
            return item
        case _:
            return value.value


print("different concrete class", concrete_mismatch(Other(9)))
