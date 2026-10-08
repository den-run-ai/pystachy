# a grab bag of classic algorithms written in the subset


def sieve(n: int) -> list[int]:
    is_p = [True] * (n + 1)
    is_p[0] = False
    is_p[1] = False
    i = 2
    while i * i <= n:
        if is_p[i]:
            for j in range(i * i, n + 1, i):
                is_p[j] = False
        i += 1
    return [k for k in range(n + 1) if is_p[k]]


def quicksort(xs: list[int]) -> list[int]:
    if len(xs) <= 1:
        return xs
    p = xs[len(xs) // 2]
    return quicksort([x for x in xs if x < p]) + [x for x in xs if x == p] + quicksort([x for x in xs if x > p])


def queens(n: int, row: int, cols: list[int]) -> int:
    if row == n:
        return 1
    count = 0
    for c in range(n):
        ok = True
        for r in range(row):
            if cols[r] == c or abs(cols[r] - c) == row - r:
                ok = False
                break
        if ok:
            cols.append(c)
            count += queens(n, row + 1, cols)
            cols.pop()
    return count


def hanoi(n: int, a: str, b: str, c: str, moves: list[str]) -> None:
    if n == 0:
        return
    hanoi(n - 1, a, c, b, moves)
    moves.append(a + c)
    hanoi(n - 1, b, a, c, moves)


def ack(m: int, n: int) -> int:
    if m == 0:
        return n + 1
    if n == 0:
        return ack(m - 1, 1)
    return ack(m - 1, ack(m, n - 1))


def lcs(a: str, b: str) -> str:
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    out: list[str] = []
    i = len(a)
    j = len(b)
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            out.append(a[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    out.reverse()
    return "".join(out)


def rpn(expr: str) -> float:
    st: list[float] = []
    for tok in expr.split():
        if tok in "+-*/":
            b = st.pop()
            a = st.pop()
            if tok == "+":
                st.append(a + b)
            elif tok == "-":
                st.append(a - b)
            elif tok == "*":
                st.append(a * b)
            else:
                st.append(a / b)
        else:
            st.append(float(tok))
    return st[0]


def bfs(grid: list[str]) -> int:
    h = len(grid)
    w = len(grid[0])
    dist: dict[int, int] = {0: 0}
    queue = [0]
    head = 0
    while head < len(queue):
        cur = queue[head]
        head += 1
        y = cur // w
        x = cur % w
        for dy, dx in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            ny = y + dy
            nx = x + dx
            if 0 <= ny < h and 0 <= nx < w and grid[ny][nx] == "." and ny * w + nx not in dist:
                dist[ny * w + nx] = dist[cur] + 1
                queue.append(ny * w + nx)
    return dist.get(h * w - 1, -1)


primes = sieve(100)
print(len(primes), primes[-5:], sum(sieve(10000)))
data = [(i * 7919) % 1000 for i in range(200)]
print(quicksort(data)[:10], quicksort(data) == sorted(data))
print([queens(n, 0, []) for n in range(1, 9)])
mv: list[str] = []
hanoi(10, "A", "B", "C", mv)
print(len(mv), mv[:5], ack(2, 3), ack(3, 3))
print(lcs("AGGTABQRSTUV", "GXTXAYBRSUV"), rpn("3 4 + 2 * 7 /"))
maze = ["..#....", ".##.##.", "....#..", "#.#...#", "..#.#.."]
print(bfs(maze), bfs([".#", "#."]))
