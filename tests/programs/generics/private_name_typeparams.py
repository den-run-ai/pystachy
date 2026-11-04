# Private type-parameter names agree with the body, parameter annotations and the parser's
# detached metadata. A private method's generic annotations remain templates after mangling.
class __Box[__T]:
    def __init__(self, __value: __T) -> None:
        self.__value = __value

    def get(self) -> __T:
        return self.__value

    def __echo[__U](self, __value: __U) -> __U:
        return __value

    def pair[__U](self, __value: __U) -> tuple[__T, __U]:
        return self.__value, self.__echo(__value)


b = __Box(4)
print(b.get(), b._Box__value, b.pair("a"), b._Box__echo(2.5))
s = __Box("text")
print(s.get(), s.pair(5))


class Quoted[__T]:
    def __init__(self, value: "__T") -> None:
        self.value = value

    def get(self) -> "__T":
        return self.value


class __Thing:
    def __init__(self, value: int) -> None:
        self.value = value


class Reader:
    def read(self, value: "__Thing") -> int:
        return value.value

    def pack[__T](self, value: __T) -> list[__T]:
        def inner(x: "__T") -> "__T":
            return x

        return [inner(value)]


print(Quoted(4).get(), Quoted("quoted").get())
print(Reader().read(__Thing(8)), Reader().pack("nested"))
