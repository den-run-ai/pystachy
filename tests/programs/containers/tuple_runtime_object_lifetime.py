# A tuple's slots keep its objects alive: trees whose children only a tuple holds, built
# between allocations that let the collector run, keep every node
class Node:
    def __init__(self, label: str, kids: tuple["Node", ...]) -> None:
        self.label = label
        self.kids = kids

    def size(self) -> int:
        return 1 + sum(k.size() for k in self.kids)


def build(depth: int, width: int) -> Node:
    if depth == 0:
        return Node("leaf", ())
    return Node(f"d{depth}", tuple(build(depth - 1, width) for _ in range(width)))


def churn(n: int) -> int:
    total = 0
    for i in range(n):
        junk = [str(j) * 3 for j in range(40)]
        total += len(junk)
    return total


trees: list[Node] = []
for r in range(12):
    trees.append(build(3, 3))
    churn(100)
print(sum(t.size() for t in trees))
kept = tuple(trees)
trees.clear()
churn(1000)
print(sum(t.size() for t in kept), kept[5].kids[1].kids[2].label)
pairs: dict[str, tuple[Node, ...]] = {}
for i in range(60):
    pairs[str(i)] = (Node(str(i), ()), Node(str(i + 1), ()))
    churn(5)
print(sum(len(v) for v in pairs.values()), pairs["42"][1].label)
