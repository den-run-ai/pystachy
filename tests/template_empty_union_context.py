def empty(n):
    return []


def empty_dict(n):
    return {}


value: list[str] | int = empty(1)
mapping: dict[str, int] | int = empty_dict(1)
optional: list[str] | int | None = empty(1)
print(value, mapping, optional)


def fill(value: list[str] | int, mapping: dict[str, int] | int) -> None:
    if isinstance(value, list):
        value.append("context")
        print(value)
    if isinstance(mapping, dict):
        mapping["key"] = 3
        print(mapping, mapping["key"])


fill(value, mapping)


def result() -> dict[tuple[str, int], int] | int:
    return empty_dict(1)


def fill_result(returned: dict[tuple[str, int], int] | int) -> None:
    if isinstance(returned, dict):
        returned["tuple", 1] = 4
        print(returned, returned["tuple", 1])


fill_result(result())
