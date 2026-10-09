# error: a call of __init__ on an object of E is not supported where F, deriving from it, defines __init__ again
class E(Exception):
    def __init__(self, n: int):
        super().__init__(n)
        self.n = n

    def reset(self) -> None:
        self.__init__(0)


class F(E):
    def __init__(self, n: int):
        super().__init__(n * 100)


f = F(1)
f.reset()
print(f.n)
