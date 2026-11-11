# Stored adapters retain their live inputs, and exhausted reversed iterators stay so.
xs = [1, 2, 3]
r = reversed(xs)
xs.append(4)
xs[2] = 30
print(next(r), list(r))
xs.append(5)
print(next(r, None))
ys = [1, 2, 3]
shrunk = reversed(ys)
ys.clear()
print(next(shrunk, None))
ys.extend([7, 8, 9])
print(next(shrunk, None))
zs = [1]
e = enumerate(zs)
zs.append(2)
print(list(e))
zs.append(3)
print(list(e))


class Mutator:
    def __init__(self, d: dict[str, int]):
        self.d = d

    def __iter__(self):
        self.d["new"] = 3
        return self

    def __next__(self) -> int:
        return 1


d = {"a": 1, "b": 2}
z = zip(d, Mutator(d))
try:
    print(next(z))
except RuntimeError as error:
    print(str(error))
