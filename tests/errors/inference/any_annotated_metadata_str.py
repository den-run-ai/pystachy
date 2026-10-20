# error: any_annotated_metadata_str.py:6: error: unsupported type annotation
# Metadata named Any must not erase a concrete Annotated type's unsupported annotation.
from typing import Annotated, Any


def f(x: Annotated[int, "Any"]) -> int:
    return 7


print(f("s"))
