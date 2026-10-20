# error: slicing an object is not supported: C.__getitem__ would take a slice object
class C:
    def __getitem__(self, k: int) -> int:
        return 1


print(C()[1:2])
