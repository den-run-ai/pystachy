# A tuple key's bool item looks up the int item it equals (also in a nested tuple, and next to a
# None), and a key the dict lacks raises CPython's KeyError, which names the key as it is, its
# bools as bools: KeyError: (True, 'zz'), not (1, 'zz')
from typing import Optional

d: dict[tuple[int, str], int] = {(1, "a"): 10, (0, "b"): 20}
e: dict[tuple[int, Optional[str]], int] = {(0, None): 1, (1, "c"): 2}
n: dict[tuple[tuple[int, int], str], int] = {((1, 0), "x"): 5}
print(d[True, "a"], d[(False, "b")], e[False, None], e[True, "c"], n[(True, False), "x"], n[(1, False), "x"])
print((True, "a") in d, d.get((False, "a"), -1), d.pop((True, "q"), -2), ((True, 0), "x") in n)
print(d[True, "zz"])
