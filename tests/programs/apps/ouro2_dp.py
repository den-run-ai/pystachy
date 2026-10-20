def edit_distance(a: str, b: str) -> int:
    prev: list[int] = []
    for j in range(len(b) + 1):
        prev.append(j)
    for i in range(1, len(a) + 1):
        cur = [i] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            cost = 1
            if a[i - 1] == b[j - 1]:
                cost = 0
            cur[j] = min(min(prev[j] + 1, cur[j - 1] + 1), prev[j - 1] + cost)
        prev = cur
    return prev[len(b)]


def lcs(a: str, b: str) -> str:
    t: list[list[int]] = []
    for i in range(len(a) + 1):
        t.append([0] * (len(b) + 1))
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                t[i][j] = t[i - 1][j - 1] + 1
            else:
                t[i][j] = max(t[i - 1][j], t[i][j - 1])
    out = ""
    i = len(a)
    j = len(b)
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            out = a[i - 1] + out
            i -= 1
            j -= 1
        elif t[i - 1][j] >= t[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return out


def knapsack(weights: list[int], values: list[int], cap: int) -> int:
    best = [0] * (cap + 1)
    for k in range(len(weights)):
        c = cap
        while c >= weights[k]:
            best[c] = max(best[c], best[c - weights[k]] + values[k])
            c -= 1
    return best[cap]


def change_ways(coins: list[int], amount: int) -> int:
    ways = [0] * (amount + 1)
    ways[0] = 1
    for c in coins:
        for a in range(c, amount + 1):
            ways[a] += ways[a - c]
    return ways[amount]


def longest_increasing(xs: list[int]) -> int:
    best = [1] * len(xs)
    top = 0
    for i in range(len(xs)):
        for j in range(i):
            if xs[j] < xs[i] and best[j] + 1 > best[i]:
                best[i] = best[j] + 1
        top = max(top, best[i])
    return top


print(edit_distance("kitten", "sitting"), edit_distance("", "abc"), edit_distance("flaw", "lawn"))
print(lcs("AGGTAB", "GXTXAYB"), lcs("the quick brown fox", "a quick brown dog"), len(lcs("abc", "xyz")))
print(knapsack([1, 3, 4, 5], [1, 4, 5, 7], 7), knapsack([10, 20, 30], [60, 100, 120], 50))
print(change_ways([1, 2, 5], 11), change_ways([1, 5, 10, 25, 50], 1000))
print(longest_increasing([10, 9, 2, 5, 3, 7, 101, 18]), longest_increasing([]))
