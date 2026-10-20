# error: expected int, got str (perhaps because collect() at line 9 returns an empty list taken as list[int]: give it a type first, as in v: list[T] = collect())
def collect(*args):
    out = []
    for a in args:
        out.append(a * 2)
    return out


xs = collect()
xs.append("s")
print(xs)
