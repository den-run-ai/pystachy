# error: lib_collections_dict_annotation_store.py:7: error: expected defaultdict[str, int], got dict[str,int]
# x: dict[K, V] = defaultdict(...) types x as the defaultdict it holds: a dict stored to it later
# is not supported (CPython's x then holds the dict)
from collections import defaultdict

x: dict[str, int] = defaultdict(int)
x = {"a": 1}
print(x)
