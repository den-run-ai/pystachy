# error: C.size() is a method of its objects: calling it through the class is not supported; call it on an object, o.size(...)
class C:
    def __init__(self) -> None:
        self.n = 1

    def size(self) -> int:
        return self.n


print(C.size(C()))
