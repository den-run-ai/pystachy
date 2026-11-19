# isinstance(x, dict) of a value that may be None or another class's object, which holds one of
# lib/collections' mappings (CPython's derive from dict): the test, and the narrowing it gives
from collections import Counter, OrderedDict, defaultdict


class Box:
    pass


def optional(x: defaultdict[str, int] | None) -> str:
    if isinstance(x, dict):
        return f"dict of {len(x)}"
    return "None"


def either(x: Box | Counter[str]) -> str:
    if isinstance(x, dict):
        return f"Counter, a: {x['a']}"
    return "Box"


def rest(x: Box | OrderedDict[str, int]) -> str:
    if isinstance(x, Box):
        return "Box"
    return f"OrderedDict, a dict: {isinstance(x, dict)}"


dd: defaultdict[str, int] = defaultdict(int)
dd["a"] += 2
print(optional(dd), optional(None))
print(either(Box()), either(Counter("aab")))
print(rest(Box()), rest(OrderedDict[str, int]()))
