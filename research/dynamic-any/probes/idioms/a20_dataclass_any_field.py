# pystachy: dynamic-any
# a dataclass with an Any field
from dataclasses import dataclass
from typing import Any


@dataclass
class Event:
    kind: str
    payload: Any


es = [Event("n", 1), Event("s", "x"), Event("l", [1, 2])]
for e in es:
    print(e.kind, e.payload)
print(es[0])
