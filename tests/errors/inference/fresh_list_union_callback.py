# error: expected int, got str
items = []
items.append(1)


def capture() -> list[int]:
    return items


alias = capture()
items.append("a")
print(alias)
