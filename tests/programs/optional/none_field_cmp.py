# A field first None, compared with None by a method compiled before the one that gives
# it a list: the comparison tests the pointer, and the list types the field.
class Cache:
    def __init__(self) -> None:
        self.data = None

    def ready(self) -> bool:
        return self.data is not None

    def fill(self, n: int) -> None:
        self.data = [i * 2 for i in range(n)]

    def get(self, i: int) -> int:
        d = self.data
        if d is None:
            return -1
        return d[i]


c = Cache()
print(c.ready(), c.get(1))
c.fill(3)
print(c.ready(), c.get(1), c.data)
