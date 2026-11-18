# pystachy: python-int
# Runtime-length tuples retain their explicit 64-bit item boundary. Keys at the
# edge of that boundary hash their actual integer, including the MIN64 slot.
for number in (-2 ** 63, -2 ** 62, 2 ** 62, 2 ** 63 - 1):
    key = tuple([number, 1])
    same = tuple([number, 1])
    d = {key: "edge"}
    print(d[key], d[same], key == same, hash(key) == hash(same), (number, 1) in d)
    print(d[key[:1] + key[1:]], key in {same}, list(d), list(d.items()))
    d[tuple([number, 2])] = "other"
    print(d.pop(same), len(d), same not in d)
