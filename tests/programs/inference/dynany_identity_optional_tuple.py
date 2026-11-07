# pystachy: dynamic-any
# Fresh dynamic tuple displays retain optional numeric objects before storage.
from typing import Any


def fresh(value: float | None) -> Any:
    return (value, value, None)


def fixed(value: float | None) -> tuple[Any, Any]:
    return (value, value)


def runtime(value: float | None) -> tuple[Any, ...]:
    return ((value, None), value, value)


def check_float(value: float | None) -> None:
    a = fresh(value)
    b = fixed(value)
    c = runtime(value)
    print("float", value, a[0] is value, a[0] is a[1],
          b[0] is value, b[0] is b[1], c[0][0] is value,
          c[1] is value, c[1] is c[2], a[2] is None)


def integer(value: int | None) -> Any:
    return (value, value, (value, None))


def boolean(value: bool | None) -> Any:
    return (value, value)


def check_bool(value: bool | None) -> None:
    flags = boolean(value)
    print("bool", flags[0] is value, flags[0] is flags[1])


def rebinding() -> None:
    value: float | None = float("1.25")
    old: Any = value

    def replace() -> float | None:
        nonlocal value
        value = float("1.25")
        return value

    items: tuple[Any, ...] = (value, value, replace(), value, (value := None))
    print("rebind", items[0] is old, items[0] is items[1],
          items[0] is items[2], items[2] is items[3], items[4] is None,
          value is None)


def retained(index: int) -> tuple[Any, Any]:
    value: float | None = float("nan") if index % 2 else float("1.25")
    return (value, (value, value))


def lifetime() -> None:
    rows: list[tuple[Any, Any]] = []
    for index in range(20):
        rows.append(retained(index))
    for index in range(50):
        garbage: Any = [str(index), (float(index), None), "churn" * 32]
    same = True
    for row in rows:
        same = same and row[0] is row[1][0] and row[1][0] is row[1][1]
    print("retained", same, rows[0][0], rows[1][0], rows[0][0] is rows[2][0])


check_float(float("1.25"))
check_float(float("-0.0"))
check_float(float("nan"))
check_float(None)
x = int("5000")
ints = integer(x)
print("int", ints[0] is x, ints[0] is ints[1], ints[2][0] is x)
print("int None", integer(None)[0] is None)
check_bool(True)
check_bool(False)
check_bool(None)
rebinding()
lifetime()
