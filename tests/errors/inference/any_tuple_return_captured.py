# error: any_tuple_return_captured.py:17: error: declared tuple return slots would require copying an existing tuple
from typing import Any
from dumpsvalues import scalar


class State:
    pass


EMPTY = (None, 'ok')


def entry(n: int, tag: Any) -> tuple[State | None, Any]:
    if n == 0:
        return None, tag
    if n == 1:
        return EMPTY
    return State(), tag


print(entry(1, scalar('str')) is EMPTY)
