# error: annotation_later_class.py:6: error: name 'Later' is not defined (the annotation runs before class Later is defined: quote it, 'Later')
from typing import NamedTuple


class P(NamedTuple):
    b: Later


class Later(NamedTuple):
    v: int


print(P(Later(1)))
