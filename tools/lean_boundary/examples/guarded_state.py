# pystachy: dynamic-any
from typing import Any


def boundary_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return False


def boundary_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""


def boundary_copy(value: Any, other: Any) -> float:
    if isinstance(value, float):
        saved: Any = value
        value = other
        if isinstance(saved, float):
            return saved
    return 0.0


def boundary_loop(value: Any, other: Any) -> bool:
    result = False
    while isinstance(value, bool):
        result = value
        value = other
        other = "finished"
    return result


print(boundary_bool(True))
print(boundary_bool("other"))
print(boundary_str("text"))
print(boundary_str(False))
print(boundary_copy(1.5, "other"))
print(boundary_copy("other", 1.5))
print(boundary_loop(True, False))
print(boundary_loop(False, True))
print(boundary_loop("finished", True))
