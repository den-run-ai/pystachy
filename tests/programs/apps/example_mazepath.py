# examples/mazepath: shortest paths through generated mazes, by breadth-first search with a
# collections.deque, as CPython finds them; then its errors, whose last line goes to stderr
import os
import tempfile

import genmaze
import mazepath

for w, h in [(11, 7), (31, 15), (61, 41)]:
    rows, width, start, end = mazepath.parse(genmaze.maze(w, h))
    parent = mazepath.search(rows, width, start)
    steps = mazepath.path(parent, end)
    depth = mazepath.depths(parent, start)
    print(w, h, width, start, end, len(steps) - 1, steps[:6], max(depth), len([p for p in parent if p >= 0]))
rows, width, start, end = mazepath.parse(["S.#", "#.#", "#.E", ""])
print(rows, width, start, end, mazepath.path(mazepath.search(rows, width, start), end))
rows, width, start, end = mazepath.parse(["S#E"])
print(mazepath.search(rows, width, start))

d = tempfile.mkdtemp()
path = os.path.join(d, "maze.txt")
with open(path, "w") as f:
    for row in genmaze.maze(21, 11):
        f.write(row + "\n")
print(mazepath.main([path]), mazepath.main(["-p", path]))
walled = os.path.join(d, "walled.txt")
with open(walled, "w") as f:
    f.write("S#.\n##.\n..E\n")
print(mazepath.main([walled]))
noend = os.path.join(d, "noend.txt")
with open(noend, "w") as f:
    f.write("S..\n")
print(mazepath.main([noend]), mazepath.main([]))
for p in [path, walled, noend]:
    os.remove(p)
os.rmdir(d)
