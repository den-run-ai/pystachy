# lists, dicts and tuples of object: appending, inserting, extending, concatenating, slicing,
# popping and deleting items, dict methods (get with a default, setdefault, pop, items, values),
# dict(zip()), comprehensions and copies keep each item as it was stored
def main() -> None:
    xs: list[object] = [1, "a"]
    xs.append(None)
    xs.insert(0, 2.5)
    xs.extend([True, b"b"])
    ys: list[object] = xs + ["tail"]
    print(xs, ys, len(ys), ys[-1], ys[1:3], ys[::-1][0])
    print(xs.pop(), xs.pop(0), xs)
    del xs[0]
    print(xs, [repr(v) for v in xs], [v for v in xs if v is not None])
    d: dict[str, object] = {"a": 1}
    d.setdefault("b", "two")
    print(d.get("a"), d.get("z"), d.get("z", 0), d.pop("a"), list(d.items()), list(d.values()), d)
    t: tuple[object, ...] = (1, "x")
    u = t + (None,)
    print(u, u[1:], list(t), tuple(xs), len(u))
    keys = ["k1", "k2"]
    vals: list[object] = [1, "v"]
    z: dict[str, object] = dict(zip(keys, vals))
    print(z, {k: v for k, v in z.items()}, [v for v in z.values()])
    w: list[object] = [i if i % 2 else str(i) for i in range(4)]
    print(w, w.copy(), list(reversed(w)))


main()
