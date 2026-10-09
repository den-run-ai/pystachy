# error: template_none_dead_branch.py:7: error: unsupported operand type(s) for +: 'int' and 'NoneType' (compiling bump(dict[int,int | None], int, None) for the call at tests/errors/template_none_dead_branch.py:15)
from typing import Optional


def bump(d, k, by):
    if k in d:
        d[k] = d[k] + by  # (compiled for the call's types, by=None, though it does not run for that call)
    else:
        d[k] = by
    return d[k]


od: dict[int, Optional[int]] = {1: None}
print(bump(od, 1, 5) if len(od) > 5 else 0)
print(bump(od, 2, None), od)  # (CPython: None {1: None, 2: None})
