# pystachy: dynamic-any
# An augmented store captures its target before index and RHS side effects,
# while its second indexing operation sees the target's current length.
from typing import Any


def run() -> None:
    first: list[int] = [10, 20, 30]
    second: list[int] = [40, 50]
    slot: Any = first
    events: list[str] = []

    def target() -> Any:
        events.append("target")
        return slot

    def index() -> int:
        nonlocal slot
        events.append("index")
        slot = second
        first.append(60)
        return -1

    def amount() -> int:
        events.append("rhs")
        first.append(70)
        return 5

    target()[index()] += amount()
    print(first, second, slot is second, events)
    events.clear()
    slots: list[Any] = [first, second]
    left: Any = slots[0]
    for i in range(4):
        try:
            if i % 2:
                left = slots[1]
                raise ValueError("switch")
            left = slots[0]
        except ValueError:
            left.append(i)
        finally:
            left[0] += 1
        typed: list[int] = left
        print(i, typed is first, typed is second, typed)
    print(first, second)


run()
