from typing import Any, Generic, TypeVar
from typing import Any as Anything
import typing
import typing_extensions

T = TypeVar("T")
Values = dict[str, Any]


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


value: Any = 5
names: list[Any] = []
names.append("ann")
table: Values = {}
table["one"] = 1
box: Box[Any] = Box(3)
quoted: "list[Any]" = [2, 4]
renamed: Anything = "alias"
qualified: typing.Any = 2.5
extended: typing_extensions.Any = True
print(value, names, table, box.value, quoted, renamed, qualified, extended)


def count_keys() -> int:
    data: dict[str, Any] = {}
    data["a"] = 1
    data["b"] = 2
    return len(data)


def local() -> str:
    x: Any = 1
    print(x + 2)
    x = "text"
    xs: list[Any] = []
    xs.append(x)
    return xs[0]


def nested(n: int) -> int:
    def inner() -> int:
        result: Any = n + 1
        return result

    return inner()


def branch(flag: bool) -> int:
    if flag:
        result: Any = 1
    else:
        result = 2
    for i in range(3):
        result += i
    return result


class Reader:
    def read(self) -> int:
        x: Any = 7
        return x


print(count_keys(), local(), nested(10), branch(True), branch(False), Reader().read())
