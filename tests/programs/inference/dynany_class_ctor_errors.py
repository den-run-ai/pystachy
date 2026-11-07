# pystachy: dynamic-any
# Binding and initializer failures belong to the selected stored class only.
from typing import Any


class Defaulted:
    def __init__(self, value: int = 4, *, enabled: bool = True) -> None:
        print("defaulted init", value, enabled)
        self.value = value
        self.enabled = enabled


class Required:
    def __init__(self, value: int, label: str) -> None:
        print("required init", value, label)
        self.value = value
        self.label = label


def one_argument(factory: Any) -> None:
    try:
        value = factory(5)
        print("made", type(value).__name__)
    except TypeError as exc:
        print("binding", exc)


# Reconstruct layouts already carried through Any by ordinary calls.
originals: list[Any] = [Defaulted(0), Required(0, "seed")]
# The same dispatcher shape has both a valid constructor and an invalid one.
one_argument(type(originals[0]))
one_argument(type(originals[1]))
defaulted: Any = type(originals[0])
value = defaulted(enabled=False)
print("defaults", value.value, value.enabled)
try:
    defaulted(1, False)
except TypeError as exc:
    print("extra positional", exc)
try:
    defaulted(1, value=2)
except TypeError as exc:
    print("duplicate argument", exc)
try:
    defaulted(unknown=3)
except TypeError as exc:
    print("unknown keyword", exc)

required: Any = type(originals[1])
try:
    required()
except TypeError as exc:
    print("missing both", exc)
try:
    required(label="named")
except TypeError as exc:
    print("missing one", exc)
value = required(label="ok", value=6)
print("after errors", value.value, value.label)


class Result:
    def __init__(self, mode: int) -> Any:
        print("result init", mode)
        if mode == 1:
            return 0
        if mode == 2:
            return ""
        return None


class Raises:
    def __init__(self, message: str) -> int:
        print("raising init", message)
        raise ValueError(message)


# Check the actual returned type, including false values, after __init__ ran.
result_original: Any = Result(0)
result: Any = type(result_original)
for mode in [0, 1, 2]:
    try:
        made = result(mode)
        print("result made", type(made) is Result)
    except TypeError as exc:
        print("result error", exc)
# A raising initializer cannot produce a seed. A static classinfo requests its
# existing boxed adapter without invoking it or inventing an instance.
probe: Any = None
assert not isinstance(probe, Raises)
raises: Any = Raises
try:
    raises("initializer first")
except ValueError as exc:
    print("raised", exc)
