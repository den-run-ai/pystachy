# error: 'b' is KW_ONLY, but KW_ONLY has already been specified
from dataclasses import KW_ONLY, dataclass


@dataclass
class P:
    x: int
    _: KW_ONLY
    y: int
    b: KW_ONLY
    z: int
