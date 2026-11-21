# error: expected int, got str
def build(n: int):
    items = []
    items.append(1)
    for i in range(n):
        items.append("a")
        alias = items
    return items


print(build(2))
