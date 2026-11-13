# error: frozenset_as_set.py:6: error: expected set[str], got frozenset[str]
def size(s: set[str]) -> int:
    return len(s)


print(size(frozenset({"a"})))
