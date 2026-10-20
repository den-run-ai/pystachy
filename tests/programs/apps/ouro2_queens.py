def place(row: int, n: int, cols: list[bool], d1: list[bool], d2: list[bool]) -> int:
    if row == n:
        return 1
    count = 0
    for c in range(n):
        a = row + c
        b = row - c + n - 1
        if not cols[c] and not d1[a] and not d2[b]:
            cols[c] = True
            d1[a] = True
            d2[b] = True
            count += place(row + 1, n, cols, d1, d2)
            cols[c] = False
            d1[a] = False
            d2[b] = False
    return count


def queens(n: int) -> int:
    return place(0, n, [False] * n, [False] * (2 * n), [False] * (2 * n))


for n in range(1, 9):
    print(n, queens(n))
