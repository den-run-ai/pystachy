# Lookup captures the union receiver before print evaluates its later arguments.
# Rendering a bound method remains deferred, while fields and properties are read now.
class Left:
    def __init__(self, value: int) -> None:
        self.value = value

    def method(self) -> int:
        return self.value

    @property
    def checked(self) -> int:
        if self.value < 0:
            raise AttributeError("negative")
        return self.value * 10

    def __repr__(self) -> str:
        return f"Left({self.value})"


class Child(Left):
    def __repr__(self) -> str:
        return f"Child({self.value})"


class Right:
    def __init__(self, value: int) -> None:
        self.value = value

    def method(self) -> int:
        return self.value

    @property
    def checked(self) -> int:
        return self.value * 100

    def __repr__(self) -> str:
        return f"Right({self.value})"


def mutate(o: Left | Right | None) -> str:
    if isinstance(o, Left):
        o.value += 1
    elif isinstance(o, Right):
        o.value += 2
    return "after"


def show(o: Left | Right | None, name: str) -> None:
    print(getattr(o, name, "missing"), mutate(o))


objects: list[Left | Right | None] = [Left(1), Child(2), Right(3), Left(-3), None]
for obj in objects:
    for name in ["method", "value", "checked", "__dict__", "__class__", "missing"]:
        print(name)
        show(obj, name)
