from dataclasses import dataclass
@dataclass(frozen=True, kw_only=True)
class P:
    x: int
print(P(x=1))
