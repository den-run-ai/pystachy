"""Finite nested JSON-shaped values use ordinary dictionaries and lists."""


def scalar(value: int | float | bool | str | None) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    return value


def visit(value: int | float | bool | str | list[int | float | bool | str | None] | dict[str, int | float | bool | str | None] | None) -> str:
    if isinstance(value, list):
        return "[" + ",".join([scalar(item) for item in value]) + "]"
    if isinstance(value, dict):
        return "{" + ",".join([key + ":" + scalar(item) for key, item in value.items()]) + "}"
    return scalar(value)


def check() -> None:
    items: list[int | float | bool | str | None] = ["agent", 3, True, None, 1.5]
    options: dict[str, int | float | bool | str | None] = {"retries": 2, "enabled": False, "token": None}
    event: dict[str, int | float | bool | str | list[int | float | bool | str | None] | dict[str, int | float | bool | str | None] | None] = {"kind": "request", "args": items, "options": options, "id": 17, "error": None}
    for key, value in event.items():
        print(key, visit(value))
    saved = event["args"]
    event["args"] = None
    if isinstance(saved, list):
        print(saved is items)
        saved.append("changed")
    print(visit(items))
    print(visit(["literal", 2, None]), visit({"literal": True, "count": 2}))
    print(visit([]), visit({}), visit([i for i in range(3)]))


def temporary() -> int | list[str]:
    return ["retained" + str(i) for i in range(4)]


def keep_box_alive() -> None:
    # The union's payload is the only remaining reference to this list.
    value = temporary()
    for i in range(150):
        garbage = [str(i) * 40]
        garbage.clear()
    if isinstance(value, list):
        print(value)


check()
keep_box_alive()
