# pystachy: dynamic-any
from typing import Any

def show(v: Any) -> None:
    print(v)


doc = {"x": 1}
show(doc)
show({"x": 1})
