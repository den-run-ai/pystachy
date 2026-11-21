# error: expected float, got str
def build(n: float):
    items = []
    items.append(n)
    items.append("tag")
    print(n in items, items.count(n))


build(float("nan"))
