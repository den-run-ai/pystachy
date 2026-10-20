# error: reflect_private_names.py:15: error: reflection over a M object is not supported: CPython mangles the name of its private attribute __x (to _ClassName__x), which Pystachy does not (#486)
class M:
    def __init__(self) -> None:
        self.__x = 1
        self.y = 2

    def peek(self) -> int:
        return self.__x


m = M()
print(m.peek())
# CPython lists _M__x: Pystachy keeps the name __x (docs/language/compatibility.md), which
# reflection would show
print(dir(m))
