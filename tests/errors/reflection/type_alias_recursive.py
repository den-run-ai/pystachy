# error: type_alias_recursive.py:7: error: recursive type aliases are not supported: 'Json' refers to itself
# (an assigned alias, through a forward reference; recursive type graphs are separate work, #121)
Json = int | str | list["Json"] | dict[str, "Json"]
Item = list[Json]


def show(j: Item) -> None:
    print(j)


show([1])
