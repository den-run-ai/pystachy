# error: Counts[k] of a bool key, with __missing__, is not supported
class Counts(dict[int, int]):
    def __missing__(self, key: int) -> int:
        return 0


c = Counts()
print(c[True])
