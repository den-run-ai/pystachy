class Base(Exception):
    def __init__(self) -> None:
        self.x = 42

    def value(self, extra: int) -> int:
        print("value body")
        return self.x + extra

    def safe(self, value: int) -> int:
        print("safe body", self is None)
        return value

    def write(self, value: int) -> None:
        print("write body")
        self.x = value

    def recurse(self, depth: int) -> int:
        if depth:
            return Base.recurse(self, depth - 1)
        return self.x


class Middle(Base):
    def invoke(self) -> int:
        return Base.value(self, argument(7))

    def safe_invoke(self) -> int:
        return Base.safe(self, argument(9))

    def write_invoke(self) -> None:
        Base.write(self, argument(11))

    def recurse_invoke(self) -> int:
        return Base.recurse(self, argument(2))


class Child(Middle):
    def chain(self) -> int:
        return Middle.invoke(self)


def receiver(present: bool) -> Child | None:
    print("receiver", present)
    return Child() if present else None


def argument(value: int) -> int:
    print("argument", value)
    return value


for present in [False, True]:
    value = receiver(present)
    print("safe", Middle.safe_invoke(value))
    try:
        print("value", Middle.invoke(value))
    except AttributeError as error:
        print("value error", str(error))
    try:
        print("chain", Child.chain(value))
    except AttributeError as error:
        print("chain error", str(error))
    try:
        Middle.write_invoke(value)
        print("write done")
    except AttributeError as error:
        print("write error", str(error))
    try:
        print("recursive", Middle.recurse_invoke(value))
    except AttributeError as error:
        print("recursive error", str(error))
