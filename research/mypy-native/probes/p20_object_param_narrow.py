# `def __eq__(self, other: object)` + isinstance narrowing from object (28 __eq__, 27 __hash__)
class Instance:
    def __init__(self, name: str) -> None:
        self.name = name
    def __hash__(self) -> int:
        return hash(self.name)
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Instance):
            return NotImplemented
        return self.name == other.name
d: dict[Instance, int] = {Instance("a"): 1}
print(Instance("a") == Instance("a"), Instance("a") == Instance("b"), d[Instance("a")], Instance("a") in {Instance("a")})
