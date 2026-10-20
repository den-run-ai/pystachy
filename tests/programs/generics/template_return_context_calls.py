# A returned display passes each call its own item context, including when the
# callee forwards another call. Different callers keep independent native layouts.
def empty(n):
    return []


def forwarded(n):
    return empty(n)


def lists(n):
    return [forwarded(n)]


words: list[list[str]] = lists(1)
numbers: list[list[int]] = lists(1)
again: list[list[str]] = lists(1)
words[0].append("word")
numbers[0].append(7)
again[0].append("again")
print(words, numbers, again, words[0] is again[0])


def mapping(n):
    return {"items": empty(n)}


values: dict[str, list[float]] = mapping(1)
values["items"].append(2.5)
print(values)


def dictionary(n):
    return {}


def shaped(n):
    return (empty(n), {(): dictionary(n)})


shape: tuple[list[str], dict[tuple[()], dict[tuple[str, int], str]]] = shaped(1)
shape[0].append("first")
shape[1][()]["key", 2] = "value"
print(shape, shape[1][()]["key", 2])


# The surrounding list's context also reaches an inherited/bound method's
# fresh result; a stored container returned by an ordinary call stays invariant.
class Factory:
    def items(self, n):
        return []


class Derived(Factory):
    pass


def methods(factory, n):
    bound = factory.items
    return [factory.items(n), bound(n)]


method_values: list[list[str]] = methods(Derived(), 1)
method_values[0].append("direct")
method_values[1].append("bound")
print(method_values)


# Callables, receivers and arguments evaluate once in their ordinary order.
def receiver(n: int) -> Derived:
    print("receiver", n)
    return Derived()


def argument(n: int) -> int:
    print("argument", n)
    return n


def ordered(n):
    return [receiver(1).items(argument(n)), receiver(2).items(argument(n + 1))]


ordered_values: list[list[str]] = ordered(3)
ordered_values[0].append("left")
ordered_values[1].append("right")
print(ordered_values)


def nullable_receiver(present: bool) -> Derived:
    print("nullable", present)
    return Derived() if present else None


def maybe_ordered(present):
    return [nullable_receiver(present).items(argument(4))]


for present in [True, False]:
    try:
        maybe_values: list[list[str]] = maybe_ordered(present)
        print(maybe_values)
    except AttributeError as error:
        print(str(error))


# A callable parameter uses its result type, not the surrounding display type.
def via_callback(callback, n):
    return (callback(n),)


callback_values: tuple[list[str]] = via_callback(empty, 1)
callback_values[0].append("callback")
print(callback_values)


def numeric(n):
    return [n, 2.5]


def mixed(n):
    return [numeric(n)]


mixed_values: list[list[int | float]] = mixed(9007199254740993)
print(mixed_values, isinstance(mixed_values[0][0], int))


# A union comparison's result hint must preserve each actual scalar/container
# type, even when it cannot use the hinted layout. Each call still runs once.
def row(n):
    print("row", n)
    return [n]


def compared(n):
    return [row(n)]


large: list[list[float]] | str = [[9007199254740992.0]]
print(large == compared(9007199254740993))
nested: list[list[int] | float] | float = [[1]]
print(nested == compared("x"), nested == compared(1))
