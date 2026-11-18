# A list subclass's __getitem__ that calls list's through super(), which a rejection fixture
# showed unsupported before.


class Stack(list[int]):
    def __getitem__(self, i: int) -> int:
        return super().__getitem__(i) + 1


s = Stack([1])
print(s[0])
