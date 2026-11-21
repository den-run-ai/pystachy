# error: any_tuple_return_prior_join.py:14: error: entry() returns both tuple[None,int | str] and tuple[State,int | str]
from typing import Any


class State:
    pass


def entry(n: int, tag: Any) -> tuple[State | None, Any]:
    if n == 0:
        return None, 'ok'
    if n == 1:
        return None, tag
    return State(), tag


print(entry(0, 3) is entry(0, 3))
