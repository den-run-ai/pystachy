# pystachy: dynamic-any
# A reducer consumer forwards erased argument sequences without knowing their size.
from typing import Any


class Labelled:
    def __init__(self, value: int = 10, label: str = "default") -> None:
        self.value = value
        self.label = label


class Empty:
    pass


class Config:
    def __init__(self, value: int, /, *, enabled: bool = True) -> None:
        self.value = value
        self.enabled = enabled


def rebuild(reduction: Any) -> Any:
    factory, args = reduction
    return factory(*args)


def rebuild_keywords(factory: Any, args: Any, kwargs: Any) -> Any:
    return factory(*args, **kwargs)


# Prepare the ordinary layouts; the consumer receives only the reducer result.
originals: list[Any] = [Labelled(), Empty(), Config(0)]
reductions: list[Any] = [
    (type(originals[0]), ()),
    (type(originals[0]), (7,)),
    (type(originals[0]), (8, "tuple")),
    (type(originals[0]), [9, "list"]),
]
for reduction in reductions:
    value = rebuild(reduction)
    print(type(value) is Labelled, value.value, value.label)
empty = rebuild((type(originals[1]), []))
print(type(empty) is Empty, empty is originals[1])

arguments: Any = [12]
keywords: Any = {"label": "mapping"}
value = rebuild_keywords(type(originals[0]), arguments, keywords)
print(value.value, value.label)
config = rebuild_keywords(type(originals[2]), [13], {"enabled": False})
print(type(config) is Config, config.value, config.enabled)

# Native lists and keyword dictionaries also feed the same runtime binder.
factory: Any = type(originals[0])
native_args: list[int] = []
for index in range(int("1")):
    native_args.append(index + 14)
native_kwargs: dict[str, str] = {"label": "native"}
value = factory(*native_args, **native_kwargs)
print(value.value, value.label)
