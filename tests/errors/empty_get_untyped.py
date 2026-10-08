# error: dict.get(key) needs a default value unless the values are objects
seen = {}
for w in ["a", "b", "a"]:
    if seen.get(w):
        print("dup", w)
    seen[w] = True
