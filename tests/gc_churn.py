# Garbage collector: allocate a few hundred MB of short-lived strings, lists, tuples, dicts
# and objects (several collections at the 32 MiB trigger, one per allocation under
# PYSTACHY_GC_STRESS=1) while linked lists with Optional next pointers, dicts of lists,
# nested lists of strings and tuples stay reachable from globals, locals, and the runtime's
# own statics (argv, the 1-character string cache); then verify every one of them.
from __future__ import annotations
from typing import Optional
import sys


class Node:
    def __init__(self, val: int, label: str, next: Optional[Node] = None):
        self.val = val
        self.label = label
        self.next = next


class Bag:
    def __init__(self, name: str):
        self.name = name
        self.items: list[tuple[int, str]] = []
        self.counts: dict[str, int] = {}


def chain(n: int, tag: str) -> Optional[Node]:
    head: Optional[Node] = None
    for i in range(n):
        head = Node(i, tag + str(i), head)
    return head


def chain_ok(head: Optional[Node], n: int, tag: str) -> bool:
    i = n - 1
    node = head
    while node is not None:
        if node.val != i or node.label != tag + str(i):
            return False
        i -= 1
        node = node.next
    return i == -1


def garbage(seed: int, n: int) -> int:
    # everything allocated here is unreachable on return
    total = 0
    for i in range(n):
        s = str(seed * 1000 + i) * 400
        parts = [s[:3], s[-3:]]
        pair = (i, Node(i, parts[0]))
        total += len(s) + len(pair[1].label)
        if i % 4 == 0:
            total += len(s * 8)
        if i % 8 == 0:
            nums = [j * i for j in range(1200)]
            total += nums[-1] % 7
        if i % 32 == 0:
            d: dict[str, list[int]] = {}
            for j in range(20):
                d["k" + str(j)] = [j, i]
            total += len(d)
    return total


def grid_ok(g: list[list[str]]) -> bool:
    for r in range(len(g)):
        for j in range(len(g[r])):
            if g[r][j] != f"{r}:{j}":
                return False
    return True


def local_roots(n: int) -> str:
    # structures reachable only from this frame while garbage() runs
    mine = chain(200, "L")
    words = [str(i) * 3 for i in range(50)]
    t = (mine, words, {"w": words})
    junk = garbage(n, 300)
    ok = chain_ok(t[0], 200, "L") and t[2]["w"][49] == "494949" and len(t[1]) == 50
    return f"{ok} {junk}"


letters = "".join([chr(65 + i) for i in range(26)])
chains: list[Optional[Node]] = []
table: dict[str, list[int]] = {}
grid: list[list[str]] = []
tuples: list[tuple[int, str, float]] = []
bags: dict[str, Bag] = {}
churn = 0
for r in range(48):
    chains.append(chain(60, "c" + str(r) + "."))
    key = "k" + str(r % 7)
    if key not in table:
        table[key] = []
    table[key].append(r * r)
    row: list[str] = []
    for j in range(12):
        row.append(str(r) + ":" + str(j))
    grid.append(row)
    tuples.append((r, "t" + str(r), r / 8))
    bname = "b" + str(r % 5)
    if bname not in bags:
        bags[bname] = Bag(bname)
    b = bags[bname]
    b.items.append((r, row[r % 12]))
    b.counts[row[0]] = b.counts.get(row[0], 0) + r
    churn += garbage(r, 600)
    if r % 16 == 0:
        print("local", local_roots(r))

print("churn", churn)
print("chains", all([chain_ok(chains[q], 60, "c" + str(q) + ".") for q in range(48)]), len(chains))
print("table", sorted(table.keys()), table["k3"], sum([len(v) for v in table.values()]))
print("grid", len(grid), grid[0][:3], grid[47][-2:], grid_ok(grid))
print("tuples", tuples[:2], tuples[-1], sum([t[2] for t in tuples]))
for name in sorted(bags.keys()):
    bag = bags[name]
    print(name, bag.name, len(bag.items), bag.items[-1], sorted(bag.counts.items())[:2])
print("letters", letters, chr(65) + chr(90), "pystachy"[2] + "pystachy"[-1])
print("argv", sys.argv[1:])
