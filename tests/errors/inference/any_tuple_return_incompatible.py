# error: any_tuple_return_incompatible.py:16: error: entry() returns both tuple[None,str] and tuple[Other,str]
from typing import Any


class State:
    pass


class Other:
    pass


def entry(flag: bool, tag: Any) -> tuple[State | None, Any]:
    if flag:
        return None, tag
    return Other(), tag


print(entry(True, "name")[1])
