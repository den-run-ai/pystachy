# error: recursive_alias_invariant.py:4: error: expected bool | dict[str,Value] | float | int | list[Value] | str | None, got list[int]
type Value = None | bool | int | float | str | list[Value] | dict[str, Value]
items: list[int] = [1]
value: Value = items

