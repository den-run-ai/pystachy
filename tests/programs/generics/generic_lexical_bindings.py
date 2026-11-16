from typing import Callable, Generic, TypeVar, TypeVarTuple
import typing as hints

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
U = TypeVar("U")
Ts = TypeVarTuple("Ts")


class Callback(Generic[T]):
    def __init__(self, read: Callable[[], T]) -> None:
        self.read: Callable[[], T] = read


def identity(value: "T") -> T:
    result: T = value
    return result


def nested(value: T):
    def middle():
        def inner():
            def read() -> T:
                result: T = value
                return result
            return Callback(read)
        return inner()
    return middle()


def item(values: dict[K, V], key: K) -> V:
    actual_key: K = key
    actual_value: V = values[actual_key]
    return actual_value


def packed(*values: *Ts):
    result: tuple[*Ts] = values
    return result


def keyword_values(**values: T) -> list[T]:
    result: list[T] = list(values.values())
    return result


class Factories:
    @classmethod
    def retain(cls, value: T):
        result: T = value
        def read() -> T:
            return result
        return Callback(read)


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def retain(self):
        def read() -> T:
            result: T = self.value
            return result
        return Callback(read)

    def replace(self, value: U):
        result: U = value
        def read() -> U:
            return result
        return Callback(read)

    def replace_new[U](self, value: U):
        result: U = value
        def read() -> U:
            return result
        return Callback(read)

    def together(self, value: U):
        def read() -> tuple[hints.Self, U]:
            return self, value
        return Callback(read)

    def together_named(self, value: U):
        def read() -> "tuple[Box, U]":
            return self, value
        return Callback(read)


class BaseFactory:
    def __init__(self, value: str) -> None:
        self.value = value

    @classmethod
    def from_value(cls, value: U):
        result: U = value
        return cls(str(result))


class ChildFactory(BaseFactory):
    pass


def shadow[T](value: T):
    kept: T = value
    def inner[T](other: T):
        typed: T = other
        def read() -> T:
            return typed
        return Callback(read)
    assert kept == value
    return inner("inner")


def enclosing_value():
    T = 17
    def identity[T](value: "T", captured=T):
        result: T = value
        assert captured == 17
        return result
    return identity("local shadow")


def repeated_name[T](value: T):
    kept: T = value
    def repeated_name[T](other: T):
        result: T = other
        return result
    assert kept == value
    return repeated_name("distinct inner type")


assert identity(7) == 7 and identity("seven") == "seven"
integers = nested(11)
words = nested("eleven")
assert integers.read() == 11 and words.read() == "eleven"
assert integers.read() == 11
assert item({"answer": 42}, "answer") == 42
assert item({2: "two"}, 2) == "two"
assert packed(1, "two", True) == (1, "two", True)
assert packed() == ()
assert keyword_values(first="a", second="b") == ["a", "b"]
assert Factories.retain(9).read() == 9
assert Factories.retain("nine").read() == "nine"
assert Box(5).retain().read() == 5
assert Box("five").retain().read() == "five"
assert Box(5).replace("other").read() == "other"
assert Box("five").replace(6).read() == 6
assert Box(5).replace_new("new").read() == "new"
assert Box("five").replace_new(7).read() == 7
owner = Box("owner")
pair = owner.together(12).read()
assert pair[0] is owner and pair[1] == 12
named_pair = owner.together_named("item").read()
assert named_pair[0] is owner and named_pair[1] == "item"
assert ChildFactory.from_value(8).value == "8"
assert shadow(1).read() == "inner"
assert enclosing_value() == "local shadow"
assert repeated_name(1) == "distinct inner type"
print("lexical locals, closures, packs, class methods and shadowing ok")
