# dictfuse (docs/typed-ir.md 7.1): a has or a getitem of a key, then a getitem or a set of the
# same key in the same dict where the key is known to be there, with no op between that may
# change a dict, share one lookup: the has becomes a pys_dict_find, the getitem a
# pys_dict_entry (both give the key's entry), and the ops after them a pys_dict_val or a
# pys_dict_entry_set of that entry. dictfuse.calls pins which calls fuse and which do not.
class Tally:
    def __init__(self) -> None:
        self.d: dict[str, int] = {}
        self.n = 0

    def add(self, k: str) -> None:
        if k in self.d:
            self.n += 1  # another field's store changes no dict
            self.d[k] += 1


def get(d: dict[str, int], k: str) -> int:
    if k in d:
        return d[k]  # find, val
    return -1


def count(d: dict[str, int], k: str) -> None:
    if k in d:
        d[k] += 1  # find, val, entry_set
    else:
        d[k] = 1  # k is not in d: a set


def put(d: dict[int, str], k: int, v: str) -> None:
    if not k in d:
        return
    d[k] = v  # find, entry_set (the has's test through a not)


def bump(d: dict[int, int], k: int) -> None:
    d[k] = d[k] + 1  # entry (a KeyError if k is not in d), val, entry_set


def twice(d: dict[str, list[int]], k: str, x: int) -> None:
    if k not in d:
        d[k] = []
    d[k].append(x)  # after the join the has's entry is not known (has, set): entry, val
    d[k].append(x)  # but the getitem's is (an append changes no dict): val


def changed(d: dict[str, int], k: str) -> None:
    if k in d:
        d.clear()
        d[k] = 0  # has, clear, set


def other(d: dict[str, int], e: dict[str, int], k: str) -> None:
    if k in d:
        e[k] = d[k]  # find, val, set: e may be another dict


def clear(d: dict[str, int]) -> None:
    d.clear()


def called(d: dict[str, int], k: str) -> int:
    if k in d:
        clear(d)  # a call that changes a dict
        return d[k]  # has, getitem
    return 0
