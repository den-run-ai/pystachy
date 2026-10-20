# error: unsupported decorator @dataclass (import dataclass from dataclasses)
@dataclass
class P:
    x: int


print(P(1))
