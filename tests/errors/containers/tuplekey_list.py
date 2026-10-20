# error: tuplekey_list.py:4: error: dict keys must be int or str, objects, or tuples of int, bool, str, str | None and objects, not tuple[int,list[int]]
seen = {}
for i in range(3):
    seen[i, [i]] = True
