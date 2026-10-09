# error: tuplekey_store_none.py:4: error: expected tuple[str,int], got tuple[str | None,int]
d: dict[tuple[str, int], int] = {("a", 1): 1}
x: str | None = None
d[x, 1] = 2  # (looked up, such a key is in no such dict; stored, the dict's keys would hold None)
print(d)
