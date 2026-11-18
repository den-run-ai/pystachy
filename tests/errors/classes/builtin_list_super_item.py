# error: list.__getitem__() of a class that derives from list is not supported
class Stack(list[int]):
    def __getitem__(self, i: int) -> int:
        return super().__getitem__(i) + 1


s = Stack([1])
print(s[0])
