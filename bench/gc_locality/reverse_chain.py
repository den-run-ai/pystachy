"""Single-root chain ordered against ascending chunk scans, plus atomic churn.

CPython and AOT: reverse_chain.py ROUNDS WIDTH [reverse|forward]
(suggested: 30 30000 reverse). Forward is a separately measured order control.
"""
import sys


class Node:
    def __init__(self, next: "Node | None", value: int):
        self.next = next
        self.value = value


def chain(width: int, mode: str) -> Node:
    head = Node(None, 0)
    if mode == "reverse":
        for i in range(1, width):
            head = Node(head, i)
    else:
        tail = head
        for i in range(1, width):
            node = Node(None, i)
            tail.next = node
            tail = node
    return head


def main():
    rounds = int(sys.argv[1])
    width = int(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 else "reverse"
    assert rounds > 0 and width > 0
    assert mode == "reverse" or mode == "forward"
    head = chain(width, mode)
    total = 0
    for r in range(rounds):
        for i in range(width):
            payload = str(i + r) * 128
            total += len(payload)
        node = head
        for i in range(width):
            assert node is not None
            expected = width - 1 - i if mode == "reverse" else i
            assert node.value == expected
            total += node.value
            node = node.next
        assert node is None
    print("chain", rounds, width, mode, total)


main()
