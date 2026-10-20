# error: recursive_alias_unguarded.py:5: error: recursive type aliases are not supported: 'Value' refers to itself
type Value = int | Value


def use(value: Value) -> None:
    print(value)


use(1)

