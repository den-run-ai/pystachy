# error: tuplekey_list.py:4: error: dict keys must be int or str, or tuples of int, bool, str and str | None items, not tuple[int,list[int]]
seen = {}
for i in range(3):
    seen[i, [i]] = True
