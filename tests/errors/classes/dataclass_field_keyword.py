# error: field() got an unexpected keyword argument 'doc'
from dataclasses import dataclass, field


@dataclass
class A:
    n: int = field(default=3, doc="count")
