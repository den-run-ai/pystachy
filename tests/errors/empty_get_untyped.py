# error: dict.get(key) needs values that can be None (str, list, dict, tuple or objects), not bool: give another default (bool | None would need boxing)
seen = {}
for w in ["a", "b", "a"]:
    if seen.get(w):
        print("dup", w)
    seen[w] = True
