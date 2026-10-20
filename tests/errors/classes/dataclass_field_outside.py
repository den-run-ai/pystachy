# error: dataclasses.field() is only supported in the body of a @dataclass class
from dataclasses import field


class A:
    n: int = field(default=3)
