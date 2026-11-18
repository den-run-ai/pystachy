# pystachy: dynamic-any
from typing import Any

class Base:
    def __init__(self, first: Any = map, second: int = 1) -> None:
        print("base initialized")

class Child(Base):
    def method(self) -> None:
        super().__init__(map, 1)
        print("done")

def invoke(o: Child) -> None:
    try:
        Child.method(o)
    except TypeError as e:
        print("TypeError:", str(e))

invoke(Child())
