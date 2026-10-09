# error: dataclasses.field is not supported
from dataclasses import dataclass, field


@dataclass
class D:
    xs: list[int] = field(default_factory=list)


print(D())
