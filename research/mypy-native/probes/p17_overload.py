# typing.overload (34 uses), e.g. mypy/types.py get_proper_type
from typing import overload
class Type:
    pass
@overload
def get_proper(t: None) -> None: ...
@overload
def get_proper(t: Type) -> Type: ...
def get_proper(t: Type | None) -> Type | None:
    return t
print(get_proper(None) is None, isinstance(get_proper(Type()), Type))
