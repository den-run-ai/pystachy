# Any in a generator's yield/return channel is inferred independently; its concrete
# send type and the remaining channel retain their declared contracts.
from typing import Any, Generator, Iterable, Iterator


def yield_any() -> Generator[Any, str | None, int]:
    sent = yield 1
    yield len(sent) if sent is not None else 0
    return 42


def yield_outer() -> Generator[Any, str | None, None]:
    result = yield from yield_any()
    print("yield result", result + 1)


g: Generator[Any, str | None, None] = yield_outer()
print(next(g), g.send("hello"))
try:
    next(g)
except StopIteration:
    print("yield done")


def return_any() -> Generator[int, str | None, Any]:
    sent = yield 10
    return sent if sent is not None else "empty"


def return_outer() -> Generator[int, str | None, None]:
    result = yield from return_any()
    print("return result", result + "!")


r = return_outer()
print(next(r))
try:
    r.send("world")
except StopIteration:
    print("return done")


def optional_return(flag: bool) -> Generator[int, None, Any]:
    yield 20
    if flag:
        return "present"


def optional_first(flag: bool) -> Generator[int, None, Any]:
    yield 30
    if flag:
        return None
    return "after"


def check_optional(flag: bool):
    result = yield from optional_return(flag)
    print("optional", result)
    result2 = yield from optional_first(flag)
    print("optional first", result2)


print(list(check_optional(True)))
print(list(check_optional(False)))


def nested() -> "Generator[list[Any], str | None, list[Any]]":
    sent = yield [1, 2]
    return [len(sent)] if sent is not None else [0]


def nested_outer() -> Generator[list[int], str | None, None]:
    result = yield from nested()
    print("nested result", result)


n = nested_outer()
print(next(n))
try:
    n.send("abc")
except StopIteration:
    print("nested done")


class Items:
    def __iter__(self) -> Iterator[Any]:
        yield 4
        yield 5


def iterable() -> Iterable[Any]:
    yield "inferred"


print(list(Items()), list(iterable()))
