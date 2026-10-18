from typing import Annotated, Any

value: Annotated[Any, "metadata"] = 7


def local() -> str:
    values: Annotated[list[Any], "items"] = []
    values.append("text")
    return values[0]


print(value, local())
