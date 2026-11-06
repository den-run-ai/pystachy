# pystachy: dynamic-any
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Item:
    name: str
    qty: int
    meta: Any


print(asdict(Item("pen", 2, {"color": "red", "w": 1.5})))
