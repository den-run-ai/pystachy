# error: runtime ** unpacking of a typed dict requires str keys; use dict[Any, Any] for other key types
# pystachy: dynamic-any
# Reboxing native non-str keys could run __hash__ again before the call's error.
from typing import Any


class Key:
    def __hash__(self) -> int:
        print("hash")
        return 31

    def __eq__(self, other: "Key") -> bool:
        return self is other


def target(value: int = 0) -> int:
    return value


mapping: dict[Key, int] = {Key(): 1}
function: Any = target
args: Any = []
try:
    function(*args, **mapping)
except TypeError:
    print("non-string key")
