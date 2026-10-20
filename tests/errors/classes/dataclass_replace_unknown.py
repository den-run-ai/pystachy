# error: P.__init__() got an unexpected keyword argument 'y'
from dataclasses import dataclass, replace


@dataclass
class P:
    x: int


print(replace(P(1), y=5))
