# A subclass of one specialization of a generic class whose __init__ binds its type variable:
# class IntBox(Box[int]) derives from Box[int], whose methods it inherits (#962).
class Box[T]:
    def __init__(self, value: T) -> None:
        self.value = value

    def get(self) -> T:
        return self.value


class IntBox(Box[int]):
    def double(self) -> int:
        return self.value * 2


b = IntBox(7)
print(b.get(), b.double(), isinstance(b, Box))
