# The key paths dictfuse (docs/typed-ir.md 7.1) meets past what the typed IR adds. A bool looked up
# among int keys (also as a tuple key's item) finds its entry with a pys_dict_find whose miss raises
# CPython's KeyError, which names the bool (pys_repr of the key as it is, pys_raise), and reads it
# with a pys_dict_val: dictfuse fuses a has, a getitem and a set, so it leaves those be. A d[k] op= v
# of a key that may be None checks it is not (KeyError: None) before the getitem and the set, which
# dictfuse fuses as it does any other key's. bool_keys.calls pins both.
from typing import Optional


def get(d: dict[int, int], b: bool) -> int:
    return d[b]  # find, repr, raise, val


def tested(d: dict[int, int], b: bool) -> int:
    if b in d:
        return d[b]  # has, then find, repr, raise, val
    return 0


def pop(d: dict[int, int], b: bool) -> int:
    return d.pop(b)  # find, repr, raise, pop


def drop(d: dict[tuple[int, str], int], b: bool) -> None:
    del d[b, "a"]  # find, repr, raise, pop


def bump(d: dict[str, int], k: Optional[str]) -> None:
    d[k] += 1  # entry, val, entry_set


def bumpn(d: dict[int, int], k: Optional[int]) -> None:
    if k in d:
        d[k] += 1  # (the has's test is a phi of k is not None: no fusion with it) entry, val, entry_set


def drop_opt(d: dict[str, int], k: Optional[str]) -> None:
    del d[k]  # pop


d = {1: 10, 0: 20, 2: 30}
print(get(d, True), tested(d, False), pop(d, True), d)
t = {(1, "a"): 1, (0, "a"): 2}
drop(t, True)
s = {"a": 1}
bump(s, "a")
n = {2: 5}
bumpn(n, 2)
bumpn(n, None)
drop_opt(s, "a")
print(t, s, n)
