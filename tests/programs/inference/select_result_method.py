# A method's selector, of a class that takes part in no inheritance, and of a class template's
# specializations.
class Store:
    def __init__(self) -> None:
        self.items = ["a", "b"]

    def get(self, i: int, whole: bool = False):
        if whole:
            return self.items
        return self.items[i]


class Box:
    def __init__(self, v):
        self.v = v

    def get(self, wrapped: bool = False):
        if wrapped:
            return [self.v]
        return self.v


s = Store()
print(s.get(0), s.get(1, True), s.get(0, whole=False).upper())
b = Box(3)
print(b.get(), b.get(True), Box("s").get(wrapped=True), Box("t").get() + "!")
