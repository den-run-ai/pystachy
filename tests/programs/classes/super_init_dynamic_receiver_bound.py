# pystachy: dynamic-any
from typing import Any

class C(Exception):
    def method(self, second: Any) -> None:
        super().__init__(C, second)
        print("done")

def invoke(o: C, value: Any) -> None:
    C.method(o, value)

invoke(C(), 7)
