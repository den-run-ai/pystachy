# del d[k] looks k up as d[k] does: a bool deletes the int key it equals, also as a tuple key's
# item, and a key the dict lacks raises CPython's KeyError, which names the key as it is
from typing import Optional

d: dict[int, int] = {1: 1, 0: 5}
if True in d:
    print(d[True])
del d[False]
print(d)
e: dict[tuple[int, Optional[str]], int] = {(1, None): 1, (0, "a"): 2}
del e[True, None]
print(e)
del e[(True, None)]
