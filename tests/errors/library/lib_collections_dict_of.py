# error: dict() of an object ('defaultdict') is not supported: make the dict with a comprehension ({k: v for k, v in x.items()})
# CPython's dict(m) copies a mapping object by its keys() and __getitem__
from collections import defaultdict

d: defaultdict[str, int] = defaultdict(int)
d["a"] += 1
print(dict(d))
