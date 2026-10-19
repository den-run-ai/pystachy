# error: recursive_alias_generic.py:5: error: recursive type aliases are not supported: 'Value' refers to itself
type Value[T] = T | list[Value[T]]


def use(value: Value[int]) -> None:
    print(value)


use(1)

