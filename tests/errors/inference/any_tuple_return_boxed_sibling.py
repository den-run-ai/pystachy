# error: any_tuple_return_boxed_sibling.py:14: error: entry() returns both tuple[State,str] and tuple[State,int]
from typing import Any


class State:
    pass


def entry(n: int, tag: Any) -> tuple[State | None, Any]:
    if n == 0:
        return None, 'ok'
    if n == 1:
        return State(), 'ok'
    return State(), tag


print(entry(0, 3) is entry(0, 3))
