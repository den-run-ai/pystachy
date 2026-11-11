# enum.Enum + @unique (mypy/nodes.py, mypy/state)
from enum import Enum, unique
@unique
class Kind(Enum):
    POS = 0
    STAR = 2
    def is_star(self) -> bool:
        return self == Kind.STAR
print(Kind.POS.is_star(), Kind.STAR.is_star(), Kind.STAR.name, Kind(0).value)
