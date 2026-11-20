# error: closed union method calls require narrowing with isinstance() first
# Dicts of two value types: no one call's arguments suit both layouts.
def put(table: dict[str, int] | dict[str, str]) -> None:
    table.clear()


put({"a": 1})
