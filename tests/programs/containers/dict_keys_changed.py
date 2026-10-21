d = {"x": 1}
for k in d:
    print(k)
    del d["x"]
    d["y"] = 2
print(d)
