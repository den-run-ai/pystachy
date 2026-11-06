# pystachy: dynamic-any
from typing import Any

def show(v: Any) -> None:
    print(v)


empty = {}
show(empty)
