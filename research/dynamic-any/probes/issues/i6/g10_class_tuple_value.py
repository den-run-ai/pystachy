ARRAY_TYPES = (list, tuple)


def is_array(x: list[int]) -> bool:
    return isinstance(x, ARRAY_TYPES)


print(is_array([1]))
