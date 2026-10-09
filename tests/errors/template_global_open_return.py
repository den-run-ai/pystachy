# error: the type of 'G' is not known yet here, before its module's code assigns it: declare it at module level first (G: T)
def helper(xs: list[str]) -> None:
    xs.append("s")


def collect(n):
    out = []
    i = 0
    while True:
        if i == n:
            return out
        if i > 5:
            print(G)
        helper(out)
        i += 1


G = collect(0)
print(collect(2), G)
