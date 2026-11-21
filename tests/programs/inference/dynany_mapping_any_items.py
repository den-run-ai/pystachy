# pystachy: dynamic-any
# an OrderedDict of Any keys and values compared with a dict, in a program that later holds a
# typed mapping as an Any value: both compile (the comparison called the operand's _dict(),
# which the typed mapping cannot answer with a boxed dict) and compare their items
from collections import Counter, OrderedDict
from typing import Any

one: Any = 1
loose: Any = OrderedDict([(one, one)])
plain: Any = {1: 1}
print(loose == plain, plain == loose, loose != plain)
counts: Any = Counter([1])
typed: Any = OrderedDict([(1, 1)])
print(loose == counts, counts == loose, loose == typed, typed == loose, counts == plain, len(counts))
