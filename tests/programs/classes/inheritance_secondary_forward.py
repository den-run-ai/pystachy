# pystachy: dynamic-any
from typing import Any, Callable


class Buffer:
    def __init__(self) -> None:
        self.data = ""


class Writer:
    def write(self, text: str) -> None:
        raise NotImplementedError

    def writelines(self, lines: list[str]) -> None:
        self.write("".join(lines))

    def pair(self, text: str) -> None:
        self.writelines([text, text])


class Plain(Buffer, Writer):
    def write(self, text: str) -> None:
        self.data += text


class Bracketed(Plain):
    def write(self, text: str) -> None:
        self.data += "[" + text + "]"


def exercise(obj: Plain, role: Writer, boxed: Any) -> None:
    obj.writelines(["a", "b"])
    role.pair("c")
    method: Callable[[str], None] = role.pair
    method("d")
    boxed.pair("e")
    callback: Any = role.pair
    callback("f")
    print(obj.data)


for item in [Plain(), Bracketed()]:
    exercise(item, item, item)
