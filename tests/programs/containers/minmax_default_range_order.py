# Range construction precedes keywords; its materialized items must follow them.
import sys
from typing import Callable


def fail_default() -> int:
    print("default")
    raise ValueError("default failed")


def fail_key() -> Callable[[int], int]:
    print("key")
    raise ValueError("key failed")


# The runtime rejects this list size before allocation, so the negative control is bounded.
try:
    print(max(range(9223372036854775807), default=fail_default()))
except ValueError as error:
    print(error)
except MemoryError:
    print("materialized before default")

try:
    print(min(range(9223372036854775807), key=fail_key(), default=0))
except ValueError as error:
    print(error)
except MemoryError:
    print("materialized before key")

try:
    print(max(range(0, 2, 0), default=fail_default()))
except ValueError as error:
    print(error)

try:
    print(max(range(0, 2, -0), default=fail_default()))
except ValueError as error:
    print(error)

try:
    print(min(range(0, 2, 00), key=fail_key(), default=0))
except ValueError as error:
    print(error)

step = len(sys.argv) - 3
try:
    print(min(range(0, 2, step), key=fail_key(), default=0))
except ValueError as error:
    print(error)

events: list[str] = []


def note(label: str, value: int) -> int:
    events.append(label)
    return value


def make_key() -> Callable[[int], int]:
    events.append("key")
    return abs


print(max(range(note("start", 0), note("stop", 3), note("step", 1)), default=note("default", -1), key=make_key()), events)
events.clear()
print(min(range(note("stop", 0)), key=make_key(), default=note("default", -1)), events)
