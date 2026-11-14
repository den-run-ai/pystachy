from typing import Any


class Converted:
    def __init__(self, value: Any) -> None:
        self.text: str = str(value)

    def get(self) -> str:
        return self.text


class Checked:
    def __init__(self, value) -> None:
        if isinstance(value, int):
            self.value: int = value
        else:
            self.value = len(value)


def show(value: Converted) -> str:
    return value.get()


print(show(Converted(7)), show(Converted("x")))
print(Checked(3).value, Checked("hello").value)
