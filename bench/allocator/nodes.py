# #650: a graph of small pointer-bearing objects that dies each step, beside a small live set
import sys
import time


class Node:
    __slots__ = ("left", "right", "value")

    def __init__(self, left: "Node | None", right: "Node | None", value: float) -> None:
        self.left = left
        self.right = right
        self.value = value


def main() -> None:
    steps = int(sys.argv[1])
    params = [Node(None, None, float(i)) for i in range(4192)]
    start = time.perf_counter()
    total = 0.0
    for step in range(steps):
        graph: list[Node] = []
        prev = params[0]
        for i in range(150000):
            prev = Node(prev, params[i % 4192], float(i))
            graph.append(prev)
        total += graph[-1].value
    print(total)
    print("TIME", time.perf_counter() - start, file=sys.stderr)


main()
