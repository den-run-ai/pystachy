class Box:
    def __init__(self) -> None:
        self.items = [1, 2, 3, 4, 5]

    def __getitem__(self, key):
        return self.items[key]

    def __setitem__(self, key: slice, value: list[int]) -> None:
        self.items[key] = value

    def __delitem__(self, key: slice) -> None:
        del self.items[key]


def make() -> Box:
    return Box()


b = make()
print(b[1], b[1:4], b[::-1])
b[1:3] = [8, 9]
print(b[:])
b[::2] = [10, 20, 30]
print(b[:])
b[1:3] += [40]
print(b[:])
del b[::-2]
print(b[:])
s = slice(1, None)
b[s] = [50, 60]
print(b[s], b[:])
b[s] += [70]
print(b[:])
del b[s]
print(b[:])
print(make()[slice(2, 4)])
make()[1:3] = [10]
del make()[1:3]
try:
    print(b[::0])
except ValueError as e:
    print(str(e))


class Narrow:
    def __getitem__(self, key: int | slice) -> int:
        if isinstance(key, slice):
            return len([10, 20, 30][key])
        return [10, 20, 30][key]


print(Narrow()[1], Narrow()[:2])
