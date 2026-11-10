# A union containing a class also includes None without an optional wrapper.
class Item:
    def __init__(self, rank: int) -> None:
        self.rank = rank


class Other:
    def __init__(self, rank: int) -> None:
        self.rank = rank


seen: list[int] = []


def by_rank(item: Item | Other) -> int:
    if isinstance(item, Item):
        rank = item.rank
    else:
        rank = item.rank
    seen.append(rank)
    return rank


high = Item(5)
low = Item(1)
middle = Other(3)
values: list[Item | Other] = [high, middle, low]
empty: list[Item | Other] = []
print(max(values, key=by_rank, default=None) is high, seen)
seen.clear()
print(min(values, key=by_rank, default=None) is low, seen)
seen.clear()
print(max(empty, key=by_rank, default=None) is None, seen)
print(min(empty, key=by_rank, default=None) is None, seen)
mixed: list[Item | Other] = [low, middle]
winner = max(mixed, key=by_rank, default=None)
print(isinstance(winner, Other), winner is middle, seen)
