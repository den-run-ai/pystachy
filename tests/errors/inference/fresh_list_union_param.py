# error: expected int, got str
def append(items: list[int]) -> None:
    items.append("a")


append([1])
