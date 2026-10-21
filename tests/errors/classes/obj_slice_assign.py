# error: slicing an object is not supported: C.__setitem__ would take a slice object
class C:
    def __setitem__(self, k: int, v: int) -> None:
        pass


C()[1:2] = [3]
