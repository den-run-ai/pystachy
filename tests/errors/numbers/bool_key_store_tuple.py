# error: bool_key_store_tuple.py:6: error: a tuple[bool,str] key is stored into a dict with tuple[int,str] keys, where CPython keeps a key it adds as the bool it is (True, not 1): convert the bool with int()
d: dict[tuple[int, str], int] = {(1, "a"): 10}


def double(b: bool, s: str) -> None:
    d[b, s] = d[b, s] * 2  # (d[int(b), s] stores the int)


double(True, "a")
print(d)
