# id() of a list, dict, set or str without dynamic Any: aliases share it, another object has
# another, and it stays an object's own while the object grows.


def main() -> None:
    xs = [1, 2, 3]
    ys = xs
    zs = [1, 2, 3]
    print(id(xs) == id(ys), id(xs) == id(zs), xs == zs)
    d = {"a": 1}
    e = d
    f = dict(d)
    print(id(d) == id(e), id(d) == id(f))
    s = {1, 2}
    t = s
    print(id(s) == id(t), id(s) == id({1, 2}))
    text = "ab" * len(xs)
    again = text
    print(id(text) == id(again))
    seen: dict[int, str] = {}
    seen[id(xs)] = "xs"
    seen[id(zs)] = "zs"
    print(seen[id(ys)], len(seen))
    before = id(xs)
    for i in range(500):
        xs.append(i)
        d[str(i)] = i
    print(id(xs) == before, id(d) == id(e), len(xs), len(d))


main()
