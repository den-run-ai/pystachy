# pystachy: dynamic-any
from typing import Any

class C(Exception):
    def method(self, first: Any) -> None:
        super().__init__(first, None)
        print("done")

def invoke(o: C, value: Any) -> None:
    C.method(o, value)

invoke(C(), int)
