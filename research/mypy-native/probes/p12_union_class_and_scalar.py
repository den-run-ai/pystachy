# e.g. mypy/nodes.py `int | str | Expression`, mypy/types.py LiteralValue = int | str | bool | float; `Type | str`
class Type:
    def __init__(self, name: str) -> None:
        self.name = name
def show(x: Type | str | None) -> str:
    if x is None:
        return "none"
    if isinstance(x, str):
        return "str:" + x
    return "type:" + x.name
print(show(Type("int")), show("s"), show(None))
