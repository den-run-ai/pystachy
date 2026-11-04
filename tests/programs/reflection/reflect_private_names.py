class M:
    def __init__(self) -> None:
        self.__x = 1
        self.y = 2

    def peek(self) -> int:
        return self.__x


m = M()
print(m.peek())
# Reflection exposes the mangled attribute; its string arguments remain literal.
print(dir(m))
print(vars(m))
print(getattr(m, "_M__x"), getattr(m, "__x", -1))


class ___:
    def __init__(self) -> None:
        self.__x = 3


print("__x" in dir(___()))
