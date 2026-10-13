"""mazepath: the shortest path through a maze, found by breadth-first search with a deque.

usage: python3 mazepath.py [-p] MAZE
       pystachy build mazepath.py -o mazepath && ./mazepath -p maze.txt

MAZE is a grid of lines: '#' is a wall, '.' an open cell, 'S' the start and 'E' the end; a path
steps up, down, left or right between open cells. mazepath searches the maze breadth first from S,
with collections.deque as the queue of cells to visit, and prints the length of the shortest path
to E (or that there is none), how many cells it reached, and the farthest of them; -p also prints
the maze with the path drawn in '*'.
"""
import sys
from collections import deque


def parse(lines: list[str]) -> tuple[list[str], int, int, int]:
    """The rows of the maze (each as wide as the widest), its width, and the cells of S and E."""
    rows = [line.rstrip("\n") for line in lines if line.strip() != ""]
    width = max([len(r) for r in rows]) if rows else 0
    rows = [r.ljust(width, "#") for r in rows]
    start = -1
    end = -1
    for y in range(len(rows)):
        x = rows[y].find("S")
        if x >= 0:
            start = y * width + x
        x = rows[y].find("E")
        if x >= 0:
            end = y * width + x
    return rows, width, start, end


def search(rows: list[str], width: int, start: int) -> list[int]:
    """The parent of each cell on a shortest path from start (start's own is itself), -1 for the
    cells it does not reach: a breadth-first search, whose queue is a deque."""
    height = len(rows)
    cells = "".join(rows)
    parent = [-1] * (width * height)
    parent[start] = start
    queue: deque[int] = deque([start])
    while queue:
        cur = queue.popleft()
        y = cur // width
        x = cur - y * width
        for nxt in (cur - width if y > 0 else -1, cur + width if y + 1 < height else -1,
                    cur - 1 if x > 0 else -1, cur + 1 if x + 1 < width else -1):
            if nxt >= 0 and parent[nxt] < 0 and cells[nxt] != "#":
                parent[nxt] = cur
                queue.append(nxt)
    return parent


def path(parent: list[int], end: int) -> list[int]:
    """The cells of the path from the start to end, by the parents search() found."""
    out: deque[int] = deque()
    cur = end
    while parent[cur] != cur:
        out.appendleft(cur)
        cur = parent[cur]
    out.appendleft(cur)
    return list(out)


def depths(parent: list[int], start: int) -> list[int]:
    """The distance of each reached cell from the start (-1 for the others)."""
    depth = [-1] * len(parent)
    depth[start] = 0
    order: deque[int] = deque([start])
    children: dict[int, list[int]] = {}
    for c in range(len(parent)):
        if parent[c] >= 0 and c != start:
            children.setdefault(parent[c], []).append(c)
    while order:
        cur = order.popleft()
        for c in children.get(cur, []):
            depth[c] = depth[cur] + 1
            order.append(c)
    return depth


def main(argv: list[str]) -> int:
    draw = len(argv) > 0 and argv[0] == "-p"
    args = argv[1:] if draw else argv
    if len(args) != 1:
        print("usage: mazepath.py [-p] MAZE", file=sys.stderr)
        return 2
    with open(args[0]) as f:
        rows, width, start, end = parse(f.readlines())
    if start < 0 or end < 0:
        print("mazepath: the maze needs an S and an E", file=sys.stderr)
        return 2
    parent = search(rows, width, start)
    reached = len([p for p in parent if p >= 0])
    depth = depths(parent, start)
    far = max(range(len(depth)), key=lambda c: depth[c])
    print(f"{width}x{len(rows)} maze, {reached} cells reached, the farthest {depth[far]} steps away at ({far % width}, {far // width})")
    if parent[end] < 0:
        print("no path from S to E")
        return 1
    steps = path(parent, end)
    print(f"shortest path from S to E: {len(steps) - 1} steps")
    if draw:
        grid = [list(r) for r in rows]
        for c in steps[1:-1]:
            grid[c // width][c % width] = "*"
        for r in grid:
            print("".join(r))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
