# pystachy: dynamic-any
# A callback invalidates a closed-over float guard even when it then raises
# into a handler and rejoins the earlier narrowed scope.
from typing import Any


def run() -> None:
    value: Any = float("2.5")

    def update(replacement: Any) -> bool:
        nonlocal value
        value = replacement
        return True

    choices: list[Any] = ["007", True, float("1.5"), int("1001")]
    for other in choices:
        value = float("2.5")
        if isinstance(value, float):
            old: Any = value
            try:
                if update(other):
                    print("changed", type(value).__name__, value)
                    raise ValueError("changed")
            except ValueError:
                print("caught", value is other, old == 2.5)
            print("rejoined", type(value).__name__, value)


run()
