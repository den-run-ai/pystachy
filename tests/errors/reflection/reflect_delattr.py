# error: reflect_delattr.py:9: error: delattr() is not supported: deleting an attribute needs an unbound state for each field (#489)
class Bag:
    def __init__(self) -> None:
        self.a = 1
        self.b = 2


bag = Bag()
delattr(bag, "a")
print(hasattr(bag, "a"))
