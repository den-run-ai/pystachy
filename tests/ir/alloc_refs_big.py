# pystachy: python-int
# allocelide in a module that opts in to promoting ints (alloc_refs_big.calls, alloc_refs.py): an int
# field is a promoting int, whose second word is an Mpz or null, and a tuple's promoting int item has
# its Mpz word in a slot of its own (utils.tslots), so both objects come from pys_alloc; a float's
# tuple still comes from pys_new


class Count:
    def __init__(self, n: int) -> None:
        self.n = n


def count(n: int) -> list[Count]:
    return [Count(n * 2**70)]


def big_pair(n: int) -> list[tuple[int, float]]:
    return [(n * 2**70, 0.5)]


def floats(x: float) -> list[tuple[float, float]]:
    return [(x, x)]


print(count(3)[0].n, big_pair(4), floats(0.25))
