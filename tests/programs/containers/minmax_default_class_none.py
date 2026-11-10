# Class types already include None. A None default must preserve the winning object's
# identity, first-item ties and one key call per item, with no key call for the default.
class Item:
    def __init__(self, rank: int, name: str) -> None:
        self.rank = rank
        self.name = name


seen: list[str] = []


def by_rank(item: Item) -> int:
    seen.append(item.name)
    return item.rank


first = Item(3, "first")
equal = Item(3, "equal")
low = Item(1, "low")
values = [first, equal, low]
empty: list[Item] = []
print(max(values, key=by_rank, default=None) is first, seen)
seen.clear()
print(min(values, default=None, key=by_rank) is low, seen)
seen.clear()
print(max(empty, key=by_rank, default=None) is None, seen)
print(min(empty, key=by_rank, default=None) is None, seen)

fallback = Item(100, "fallback")
print(max(empty, key=by_rank, default=fallback) is fallback, seen)
print(max(values, key=by_rank, default=fallback) is first, seen)
winner = max(values, key=lambda item: item.rank, default=None)
if winner is not None:
    winner.rank = 7
print(first.rank, winner is first)
