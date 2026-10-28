# error: __hash__ must return int, and Name.__hash__() returns str
class Name:
    def __init__(self, s: str) -> None:
        self.s = s

    def __hash__(self):
        return self.s


print(hash(Name("a")))
