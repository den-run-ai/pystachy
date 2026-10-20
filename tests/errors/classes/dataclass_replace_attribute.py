# error: Own.__init__() got an unexpected keyword argument 'extra'
from dataclasses import dataclass, replace


@dataclass
class Own:
    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        self.extra = 0


print(replace(Own("a"), extra=5))
