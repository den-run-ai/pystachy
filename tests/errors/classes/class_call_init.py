# error: C.__init__() is a method of its objects: calling it through the class is not supported; call it on an object, o.__init__(...)
class C:
    def __init__(self, n: int) -> None:
        self.n = n


c = C(1)
C.__init__(c, 2)
print(c.n)
