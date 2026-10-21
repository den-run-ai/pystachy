from typing import Any


def ident(x: Any) -> Any:
    return x


class Holder:
    def __init__(self, value: Any) -> None:
        self.value = value
