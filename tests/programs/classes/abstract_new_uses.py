# Making an object of a class with abstract methods raises CPython's TypeError also where the
# expression goes on to use the object: printed, str(), repr(), an f-string, hash() and
# isinstance() (#1618: the code that used it named the block the raise had ended as the
# predecessor of a phi, which LLVM rejected)
from abc import ABC, abstractmethod


class Half(ABC):
    @abstractmethod
    def f(self) -> int:
        return 0

    @abstractmethod
    def g(self) -> int:
        return 0


class Full(Half):
    def f(self) -> int:
        return 1

    def g(self) -> int:
        return 2


def attempt(what: str) -> None:
    try:
        if what == "print":
            print(Half())
        elif what == "str":
            print(len(str(Half())))
        elif what == "repr":
            print(repr(Half()))
        elif what == "format":
            print(f"<{Half()}>")
        elif what == "hash":
            print(hash(Half()) == 0)
        else:
            print(isinstance(Half(), Full))
    except TypeError as e:
        print(what, e)


for what in ["print", "str", "repr", "format", "hash", "isinstance"]:
    attempt(what)
try:
    print(Half())
except TypeError as e:
    print("module", e)
print(Full().f() + Full().g(), isinstance(Full(), Half))
