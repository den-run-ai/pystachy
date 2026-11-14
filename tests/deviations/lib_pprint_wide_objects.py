# Documented deviation: pprint writes an object of a dataclass or of a collections class as its
# repr(), on one line, also where that is wider than the width. CPython wraps a dataclass's
# fields and the items of a deque, an OrderedDict, a defaultdict or a Counter.
import pprint
from collections import deque
from dataclasses import dataclass


@dataclass
class Row:
    name: str
    values: list[int]


print(pprint.pformat(Row("first", [1, 2, 3]), width=20))
print(pprint.pformat([Row("a", [1])], width=12))
print(pprint.pformat(deque([10, 20, 30]), width=10))
