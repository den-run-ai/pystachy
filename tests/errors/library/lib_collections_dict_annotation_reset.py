# error: lib_collections_dict_annotation_reset.py:12: error: cannot infer the type of an empty dict
# self.m: dict[K, V] = defaultdict(...) types the field as the defaultdict it holds: an empty
# dict stored to it later is not supported (CPython's field then holds the dict)
from collections import defaultdict


class Groups:
    def __init__(self) -> None:
        self.m: dict[str, list[int]] = defaultdict(list)

    def clear(self) -> None:
        self.m = {}


g = Groups()
g.clear()
print(g.m)
