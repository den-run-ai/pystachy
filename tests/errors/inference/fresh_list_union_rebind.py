# error: expected int, got str
def build():
    items = []
    items.append(1)
    alias = items
    items = []
    items.append(2)
    items.append("a")
    return alias


print(build())
