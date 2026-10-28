# pystachy: python-int
# A quoted annotation stays a forward reference, which CPython does not evaluate
# when the def runs; its int names the promoting value as an unquoted one does.


class Node:
    def __init__(self, value: int, rest: "Node | None") -> None:
        self.value = value
        self.rest = rest

    def total(self) -> "int":
        rest = self.rest
        return self.value if rest is None else self.value + rest.total()


def tally(values: "list[int]") -> "dict[str, int]":
    return {"sum": sum(values), "max": max(values)}


chain = Node(9223372036854775807, Node(2 ** 63, Node(1, None)))
print(chain.total())
print(tally([2 ** 64, 5, -(2 ** 70)]))
