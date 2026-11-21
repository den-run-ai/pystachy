# A dictionary's length stays an integer when returned as a closed union,
# including when a tag selects the dictionary from a container union.
def dict_size(items: dict[str, int]) -> int | str:
    return len(items)


def container_size(items: dict[str, int] | list[int]) -> int | str:
    return len(items)


print(dict_size({"x": 3}), container_size({"a": 1, "b": 2}), container_size([4, 5, 6]))
