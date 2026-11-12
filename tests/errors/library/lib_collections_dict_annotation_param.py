# error: lib_collections_dict_annotation_param.py:12: error: expected dict[str,int], got defaultdict[str, int]
# x: dict[K, V] = defaultdict(...) types x as the defaultdict it holds: x passed where a dict
# is expected is not supported (CPython's defaultdict is a dict)
from collections import defaultdict


def size(d: dict[str, int]) -> int:
    return len(d)


x: dict[str, int] = defaultdict(int)
print(size(x))
