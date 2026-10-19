type Tree = int | str | list[Tree] | dict[str, Tree]


def make() -> Tree:
    return {"a": [1, "text", {"b": []}]}

