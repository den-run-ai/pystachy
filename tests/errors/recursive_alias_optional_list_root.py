# error: recursive_alias_optional_list_root.py:5: error: recursive type aliases are not supported: 'Value' refers to itself
type Value = None | list[Value]


def use(value: Value) -> None:
    print(value)


use([])

