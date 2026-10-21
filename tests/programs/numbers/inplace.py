class V:
    def __init__(self, x: int):
        self.x = x

    def __add__(self, o: "V") -> "V":
        return V(self.x + o.x)

    def __iadd__(self, o: "V") -> "V":
        self.x += o.x
        return self


a = V(1)
b = a
a += V(2)
print(a.x, b.x, a is b)
xs = [1, 2]
ys = xs
xs *= 2
print(ys)
d: dict[str, list[int]] = {"a": [1]}
alias = d["a"]
d["a"] += [2]
print(alias)
m = [[1], [2]]
inner = m[1]
m[1] += [7]
m[0] *= 3
print(inner, m)
zs = [5]
zs *= 0
print(zs)
