# error: expected int, got str
# pystachy: python-int
def build(n: int):
    items = []
    items.append(n)
    items.append("tag")
    return items


print(build(2**100))
