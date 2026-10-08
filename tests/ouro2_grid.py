from __future__ import annotations

# Breadth-first search through a maze, then a few generations of Life.


class Cell:
    r: int
    c: int
    dist: int

    def __init__(self, r: int, c: int, dist: int) -> None:
        self.r = r
        self.c = c
        self.dist = dist


def shortest(maze: list[str]) -> int:
    rows = len(maze)
    cols = len(maze[0])
    seen: list[list[bool]] = []
    queue: list[Cell] = []
    for r in range(rows):
        seen.append([False] * cols)
        for c in range(cols):
            if maze[r][c] == "S":
                queue.append(Cell(r, c, 0))
                seen[r][c] = True
    head = 0
    dr = [1, -1, 0, 0]
    dc = [0, 0, 1, -1]
    while head < len(queue):
        cur = queue[head]
        head += 1
        if maze[cur.r][cur.c] == "E":
            return cur.dist
        for k in range(4):
            r = cur.r + dr[k]
            c = cur.c + dc[k]
            if r >= 0 and r < rows and c >= 0 and c < cols and maze[r][c] != "#" and not seen[r][c]:
                seen[r][c] = True
                queue.append(Cell(r, c, cur.dist + 1))
    return -1


def step(g: list[list[bool]]) -> list[list[bool]]:
    n = len(g)
    out: list[list[bool]] = []
    for r in range(n):
        row = [False] * n
        for c in range(n):
            near = 0
            for i in range(-1, 2):
                for j in range(-1, 2):
                    if (i != 0 or j != 0) and g[(r + i) % n][(c + j) % n]:
                        near += 1
            row[c] = near == 3 or (near == 2 and g[r][c])
        out.append(row)
    return out


def show(g: list[list[bool]]) -> None:
    for row in g:
        line = ""
        for alive in row:
            if alive:
                line = line + "#"
            else:
                line = line + "."
        print(line)


maze = ["S..#....",
        ".#.#.##.",
        ".#...#..",
        ".####.#.",
        "......#E"]
print(shortest(maze), shortest(["S#E"]), shortest(["SE"]))
g: list[list[bool]] = []
for r in range(6):
    g.append([False] * 6)
g[0][1] = True
g[1][2] = True
g[2][0] = True
g[2][1] = True
g[2][2] = True
for gen in range(4):
    g = step(g)
show(g)
