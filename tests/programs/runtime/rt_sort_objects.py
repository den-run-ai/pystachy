from dataclasses import dataclass


@dataclass
class P:
    x: int


ps = [P(2), P(1)]
print(ps)
print(sorted(ps))
