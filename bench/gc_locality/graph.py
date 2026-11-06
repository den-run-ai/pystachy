"""Stable permuted graph beside repeatedly allocated linked chains.

CPython and native AOT: graph.py ROUNDS WIDTH (suggested: 30 30000).
"""
import sys


class Node:
    def __init__(self, left: "Node | None", right: "Node | None", value: int):
        self.left = left
        self.right = right
        self.value = value


def main():
    rounds = int(sys.argv[1])
    width = int(sys.argv[2])
    assert rounds > 0 and width > 0
    live = [Node(None, None, i) for i in range(width)]
    for i in range(width):
        live[i].left = live[(i * 17 + 1) % width]
        live[i].right = live[(i * 31 + 7) % width]
    total = 0
    for r in range(rounds):
        head = live[r % width]
        for i in range(width * 2):
            head = Node(head, live[(i * 13 + r) % width], i + r)
        node = head
        for i in range(width * 2):
            left = node.left
            right = node.right
            assert left is not None and right is not None
            total += node.value + right.value
            node = left
    for i in range(width):
        left = live[i].left
        right = live[i].right
        assert left is live[(i * 17 + 1) % width]
        assert right is live[(i * 31 + 7) % width]
    print("graph", rounds, width, total)


main()
