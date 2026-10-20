# error: type_alias_annotation_unbound.py:3: error: name 'TypeAlias' is not defined (import it from typing)
# (CPython evaluates the annotation of name: TypeAlias = value, after the value)
Row: TypeAlias = list[str]
from typing import TypeAlias  # noqa: E402

print("never")
