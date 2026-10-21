# Constructor annotations containing Any and direct object parameters use the same field
# specialization as unannotated parameters; other annotations still constrain their arguments.
from typing import Any, Any as Anything
import typing


class Holder:
    def __init__(self, value: Any) -> None:
        self.value = value

    def get(self) -> Any:
        return self.value


class ObjectHolder:
    def __init__(self, value: object) -> None:
        self.value = value


class Nested:
    def __init__(self, values: "list[Any]", named: dict[str, typing.Any]) -> None:
        self.values = values
        self.named = named


class Defaulted:
    def __init__(self, value: Anything = 7, /, *, label: str = "default") -> None:
        self.value = value
        self.label = label


class Variadic:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


def make(value: Any) -> Holder:
    return Holder(value)


a = Holder(1)
b = Holder("s")
a.value = 2
print(a.get(), b.get(), Holder(3).get(), isinstance(a, Holder), isinstance(b, Holder))
print(make(4).get(), make("made").get())
print(ObjectHolder(5).value, ObjectHolder("object").value)
print(Nested([1, 2], {"x": 3}).values, Nested(["a"], {"x": "b"}).named)
print(Defaulted().value, Defaulted().label, Defaulted("text", label="named").value)
print(Variadic(1, "two", label="three").args)
print(Variadic(1, "two", label="three").kwargs["label"])
