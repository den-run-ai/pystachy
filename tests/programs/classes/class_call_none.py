# An explicit class-method call evaluates arguments and passes None as self. Only an
# operation in the method body may reject it; ordinary attribute calls still guard first.
class C:
    def __init__(self) -> None:
        self.value = 7

    def ignore(self, x: int, *, y: int = 0) -> int:
        print("body", self is None)
        return x + y

    def read(self, x: int) -> int:
        print("read body", x)
        return self.value

    def write(self, x: int) -> None:
        print("write body", x)
        self.value = x


def receiver(present: bool) -> C | None:
    print("receiver", present)
    return C() if present else None


def argument(label: str, fails: bool = False) -> int:
    print("argument", label)
    if fails:
        raise ValueError(label)
    return len(label)


for present in [False, True]:
    try:
        print("result", C.ignore(receiver(present), argument("first"), y=argument("second")))
    except AttributeError as error:
        print("unexpected", str(error))
    try:
        C.ignore(receiver(present), argument("raises", True), y=argument("skipped"))
    except ValueError as error:
        print("argument error", str(error))
    except AttributeError as error:
        print("unexpected", str(error))
    try:
        print("read", C.read(receiver(present), argument("read")))
    except AttributeError as error:
        print("read error", str(error))
    try:
        C.write(receiver(present), argument("write"))
    except AttributeError as error:
        print("write error", str(error))
    try:
        print("bound", receiver(present).ignore(argument("bound")))
    except AttributeError as error:
        print("lookup error", str(error))


class Child(C):
    def ignore(self, x: int, *, y: int = 0) -> int:
        return 1000


print("base implementation", C.ignore(Child(), 1, y=2))


# A class outside a hierarchy uses a concrete method signature, not a receiver template.
class Plain:
    def __init__(self) -> None:
        self.value = 23

    def ignore(self, x: int) -> int:
        print("plain body", self is None)
        return x

    def read(self, x: int) -> int:
        print("plain read", x)
        return self.value


def plain_receiver() -> Plain | None:
    return None


try:
    print("plain result", Plain.ignore(plain_receiver(), argument("plain")))
except AttributeError as error:
    print("unexpected", str(error))
try:
    Plain.read(plain_receiver(), argument("plain read"))
except AttributeError as error:
    print("plain error", str(error))
