# A field stored from tuple(xs) of a list is a runtime-length tuple of the list's items (of a
# string, of its characters; tuple() of a tuple is that tuple)
class Leaf:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"Leaf({self.n})"


class Holder:
    def __init__(self, nums: list[int], words: list[str], leaves: list[Leaf], text: str, pair: tuple[int, str]) -> None:
        self.nums = tuple(nums)
        self.words = tuple(words)
        self.leaves = tuple(leaves)
        self.chars = tuple(text)
        self.pair = tuple(pair)


nums = [1, 2]
h = Holder(nums, ["a"], [Leaf(3), Leaf(4)], "xy", (5, "z"))
nums.append(3)
print(h.nums, h.words, h.leaves, h.chars, h.pair)
print(len(h.leaves), h.leaves[1].n, h.pair[1])
h.leaves = h.leaves + (Leaf(5),)
print(h.leaves)
