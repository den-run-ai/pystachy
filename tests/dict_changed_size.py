d = {"a": 1, "b": 2}
for k in d:
    print(k)
    if k == "a":
        d["c"] = 3
print(d)
