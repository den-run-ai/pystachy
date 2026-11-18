# error: expected int, got I
# list.insert() of an object index is not supported: CPython asks it for __index__() once the
# value is evaluated too.
class I:
    def __index__(self) -> int:
        print("index")
        return 0


def value() -> int:
    print("value")
    return 7


xs = []
xs.insert(I(), value())
print(xs)
