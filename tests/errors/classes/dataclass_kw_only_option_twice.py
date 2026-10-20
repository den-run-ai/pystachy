# error: '__' is KW_ONLY, but KW_ONLY has already been specified
from dataclasses import KW_ONLY, dataclass


@dataclass(kw_only=True)
class P:
    a: int
    _: KW_ONLY
    b: int = 1
    __: KW_ONLY
    c: int = 2
