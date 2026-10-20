# error: any_annotated_metadata_name.py:6: error: unsupported type annotation
# Even typing.Any itself is metadata in this position, not the annotated type.
import typing as t


def f(x: t.Annotated[int, t.Any]) -> int:
    return 7


print(f("s"))
