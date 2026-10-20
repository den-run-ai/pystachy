# error: annotation_dict_arity.py:8: error: Too few arguments for typing.Dict; actual 1, expected 2 (CPython evaluates this annotation when the class body runs
# typing.Dict takes a key and a value type: Dict[str] in a class body is CPython's TypeError when
# the class statement runs.
from typing import Dict


class Table:
    rows: Dict[str]


print(Table())
