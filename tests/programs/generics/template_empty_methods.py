# Expected result types reach user methods and callable fields, while each fresh
# empty result retains its caller's layout rather than changing the method body.
class Factory:
    def empty(self, n):
        return []

    def mapping(self, n):
        return {}

    def flags(self, n):
        return set()

    def forward(self, n):
        return self.mapping(n)

    def again(self, n):
        return self.forward(n)

    def maybe_filled(self, present):
        if present:
            return self.mapping(1)
        return {("filled", 1): 9}

    def __call__(self, n):
        return self.empty(n)

    @staticmethod
    def static(n):
        return []

    @classmethod
    def class_method(cls, n):
        return {}


class Holder:
    def __init__(self, factory: Factory) -> None:
        self.factory = factory


factory = Factory()
words: list[str] = Factory().empty(1)
numbers: list[int] = factory.empty(1)
words.append("word")
numbers.append(2)
print(words, numbers, factory.empty(1))

bound = factory.mapping
names: dict[str, int] = bound(1)
keys: dict[tuple[str, int], str] = factory.again(1)
names["name"] = 3
keys["key", 4] = "value"
print(names, keys, keys["key", 4], factory.again(1))

flags: set[tuple[str, int]] = factory.flags(1)
flags.add(("flag", 5))
print(("flag", 5) in flags, len(factory.flags(1)))

called: list[str] = factory(1)
explicit: list[str] = factory.__call__(1)
field: list[str] = Holder(factory).factory(1)
called.append("call")
explicit.append("explicit")
field.append("field")
print(called, explicit, field)

static: list[str] = factory.static(1)
cls: dict[str, int] = factory.class_method(1)
static.append("static")
cls["class"] = 6
print(static, cls)


def annotated(factory: Factory) -> dict[str, int]:
    return factory.again(1)


def forwarded(factory, n):
    return factory.again(n)


value: dict[str, int] | int = annotated(factory)
other: dict[tuple[str, int], int] = forwarded(factory, 1)
other["forward", 7] = 8
print(value, other)

deferred = factory.maybe_filled(True)
deferred["empty", 2] = 10
print(deferred, factory.maybe_filled(False), factory.mapping(1))


# A filled result keeps its existing inferred or annotated type.
class Filled:
    def items(self, value):
        return [value]

    def declared(self, value) -> list[int]:
        return [value]


print(Filled().items("filled"), Filled().declared(9))
