# isinstance() of lib/collections' mappings: CPython's derive from dict, so each object is a dict
# (also in a tuple or union of types), though its type is its own class, not dict
from collections import Counter, OrderedDict, defaultdict

x: defaultdict[str, set[str]] = defaultdict(set)
x["k"].add("v")
od: OrderedDict[str, int] = OrderedDict([("a", 1)])
c = Counter("abca")
print(isinstance(x, dict), isinstance(od, dict), isinstance(c, dict))
print(isinstance(x, (dict, list)), isinstance(od, (list, dict)), isinstance(c, list | dict))
print(isinstance(x, list), isinstance(od, (list, tuple)), isinstance(c, set | frozenset))
print(type(x) is dict, type(od) is dict, type(c) is dict, type(x) == dict)
print(type(x) is defaultdict, type(od) is OrderedDict, type(c) is Counter)
print(isinstance(x, defaultdict), isinstance(od, Counter), isinstance(c, OrderedDict))
if isinstance(x, dict):
    print("x is a dict:", sorted(x["k"]))
else:
    print("x is no dict")
if not isinstance(c, dict):
    print("c is no dict")
else:
    print("c is a dict:", c["a"])
