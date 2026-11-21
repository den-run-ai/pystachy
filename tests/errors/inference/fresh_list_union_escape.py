# error: expected int, got str

def build():
    items = []
    items.append(1)
    alias = items
    items.append("a")
    return alias


print(build())
