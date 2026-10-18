# error: any_annotated_metadata_import.py:6: error: unsupported type annotation
# The metadata rule also applies to a renamed backport import.
from typing_extensions import Annotated as Marked, Any


def f(x: Marked[int, Any]) -> int:
    return 7


print(f("s"))
