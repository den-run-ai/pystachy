# Explicit calls of __str__ and __repr__ on an exception are str() and repr(): those of the class
# of its object, which may derive from its static type, or the builtin ones it inherits.
class E(Exception):
    def __repr__(self) -> str:
        return "E"

    def show(self) -> str:
        return self.__repr__() + "/" + self.__str__()


class F(E):
    def __repr__(self) -> str:
        return "F"

    def __str__(self) -> str:
        return "F!"


class G(Exception):
    pass


print(F().show(), E("e").show())
f: E = F("n")
print(f.__str__(), f.__repr__())
g = G("m")
print(g.__str__(), g.__repr__())
try:
    raise F()
except Exception as e:
    print(e.__str__(), e.__repr__(), ValueError("v").__str__(), ValueError("v").__repr__())
