from dataclasses import dataclass
@dataclass(kw_only=True)
class P:
    x: int
print(P(x=1))
