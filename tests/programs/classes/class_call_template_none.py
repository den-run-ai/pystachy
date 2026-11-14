# Nullable receivers retain their class-template specialization for explicit calls.
class Box:
    def __init__(self, value):
        self.value = value

    def ignore(self, x: int) -> int:
        print("template body", self is None)
        return x

    def read(self, x: int) -> str:
        print("template read", x)
        return str(self.value)


def argument() -> int:
    print("template argument")
    return 3


def check(present: bool) -> None:
    box = Box(17)
    if not present:
        box = None
    try:
        print(Box.ignore(box, argument()))
    except AttributeError as error:
        print("unexpected", str(error))
    try:
        print(Box.read(box, argument()))
    except AttributeError as error:
        print("template error", str(error))


check(False)
check(True)
