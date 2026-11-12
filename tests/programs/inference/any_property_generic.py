from typing import Any


class Box:
    def __init__(self, value):
        self.value_ = value

    @property
    def value(self) -> Any:
        return self.value_


print(Box(5).value + 1)
print(Box("five").value.upper())
data = ["kept"]
box = Box(data)
print(box.value is data)
box.value.append("alive")
print(data)
