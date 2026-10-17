from typing import Any

values: dict[str, Any] = {}
values["first"] = 9


def read() -> int:
    result: Any = values["first"]
    return result
