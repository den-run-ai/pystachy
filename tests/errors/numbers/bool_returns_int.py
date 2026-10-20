# error: __bool__ should return bool, returned int
class C:
    def __bool__(self) -> int:
        return 1


print(bool(C()))
