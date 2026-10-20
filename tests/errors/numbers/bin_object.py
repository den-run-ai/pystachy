# error: 'C' object cannot be interpreted as an integer
class C:
    def __init__(self) -> None:
        self.n = 3


print(bin(C()))
