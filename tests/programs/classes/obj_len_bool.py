# a __len__ that returns a bool gives len() the int it is, as CPython's len() takes it
class C:
    def __init__(self, b: bool) -> None:
        self.b = b

    def __len__(self) -> bool:
        return self.b


print(len(C(True)), len(C(False)), bool(C(True)), bool(C(False)), "y" if C(True) else "n", not C(False))
