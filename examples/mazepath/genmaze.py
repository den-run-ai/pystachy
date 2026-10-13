"""genmaze: a synthetic maze for mazepath.py, the same on every run.

usage: python3 genmaze.py W H > MAZE
A W x H grid (W and H odd) carved by a randomized depth-first search into a perfect maze (one path
between any two cells), with one wall in 8 then knocked out to make loops, S at the top left and E
at the bottom right.
"""
import sys

seed = 20261013


def rand(n: int) -> int:
    # an int in [0, n): a 31-bit linear congruential generator (glibc's constants), whose products
    # stay in 64 bits, as Pystachy's ints do
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return (seed >> 8) % n


def maze(w: int, h: int) -> list[str]:
    grid = [["#"] * w for _ in range(h)]
    stack = [(1, 1)]
    grid[1][1] = "."
    while stack:
        x, y = stack[-1]
        options: list[tuple[int, int]] = []
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            nx = x + dx
            ny = y + dy
            if 0 < nx < w - 1 and 0 < ny < h - 1 and grid[ny][nx] == "#":
                options.append((nx, ny))
        if not options:
            stack.pop()
            continue
        nx, ny = options[rand(len(options))]
        grid[(y + ny) // 2][(x + nx) // 2] = "."
        grid[ny][nx] = "."
        stack.append((nx, ny))
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if grid[y][x] == "#" and (x + y) % 2 == 1 and rand(8) == 0:
                grid[y][x] = "."
    grid[1][1] = "S"
    grid[h - 2][w - 2] = "E"
    return ["".join(row) for row in grid]


def main() -> None:
    for row in maze(int(sys.argv[1]), int(sys.argv[2])):
        print(row)


if __name__ == "__main__":
    main()
