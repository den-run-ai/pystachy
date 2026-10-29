# pystachy: python-int
# Retired entries must lose both wide companions before the next key reuses their slot.
big = 2 ** 80
edge = -2 ** 63


def refill(d: dict[str, int]) -> None:
    d["wide"] = big
    d["hole"] = big + 1
    del d["hole"]
    print(d.popitem())
    d["edge"] = edge
    print(d["edge"], d.popitem(), len(d))
    d["wide"] = big
    print(d.pop("wide"))
    d.setdefault("edge", edge)
    print(d.popitem())


values: dict[str, int] = {}
refill(values)
values.update({"wide": big})
refill(values.copy())
refill(dict(values))
values.clear()
refill(values)

both: dict[int, int] = {big: big, big + 1: big + 2}
del both[big + 1]
print(both.popitem())
both[edge] = edge
print(both, both[edge], both.popitem(), len(both))
both[big] = big
both[big] = edge
print(both[big], both.popitem())
