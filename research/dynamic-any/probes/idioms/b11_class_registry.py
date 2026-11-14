# pystachy: dynamic-any
# a plugin registry of classes, instantiated by name
from typing import Any


class A:
    def run(self) -> str:
        return "A"


class B:
    def run(self) -> str:
        return "B"


REGISTRY: dict[str, Any] = {"a": A, "b": B}
for name in ["a", "b"]:
    print(REGISTRY[name]().run())
