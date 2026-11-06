# pystachy: dynamic-any
from typing import Any


class Ctx:
    def __enter__(self) -> "Ctx":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        print("exit", exc_type is None)


with Ctx():
    print("in")
