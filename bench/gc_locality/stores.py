"""Replace references in long-lived object, list, and dictionary containers.

CPython and native AOT: stores.py ROUNDS WIDTH (suggested: 100 20000).
"""
import sys


class Box:
    def __init__(self, values: list[int], label: str):
        self.values = values
        self.label = label


def main():
    rounds = int(sys.argv[1])
    width = int(sys.argv[2])
    assert rounds > 0 and width > 0
    live = [Box([i, i + 1], str(i)) for i in range(width)]
    table: dict[int, Box] = {i: live[i] for i in range(width)}
    saved: list[list[int]] = []
    total = 0
    for r in range(rounds):
        for i in range(width):
            old = table[i]
            old.values.append(r)
            new = Box([old.values[0] + 1, i, r], str(i + r))
            live[i] = new
            if i % 8 == 0:
                del table[i]
            table[i] = new
            total += old.values[-1] + len(new.label)
        saved.append(table[r % width].values)
    for i in range(width):
        assert table[i] is live[i]
        assert live[i].values[0] == i + rounds
        assert live[i].values[1] == i
        total += live[i].values[0]
    for r in range(rounds):
        assert saved[r][0] == r % width + r + 1
        total += saved[r][0]
    print("stores", rounds, width, total, len(table), len(saved))


main()
