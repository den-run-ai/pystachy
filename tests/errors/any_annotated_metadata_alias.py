# error: any_annotated_metadata_alias.py:8: error: unsupported type annotation
# Type-alias expansion preserves the distinction between the type and metadata.
from typing import Annotated, Any

type Marked = Annotated[int, Any]


def f(x: Marked) -> int:
    return 7


print(f("s"))
