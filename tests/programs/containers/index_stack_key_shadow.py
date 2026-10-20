# Gen.stack_key reads len(x) and isinstance(x, C) as a read of x only where they are the
# builtins: this program's len keeps what it is given, so a __getitem__ that calls it gets a
# heap tuple that outlives the call
kept: list[tuple[int, int]] = []


def len(t: tuple[int, int]) -> int:
    kept.append(t)
    return 2


class Grid:
    def __getitem__(self, key: tuple[int, int]) -> int:
        return len(key) + key[0] * 10 + key[1]


g = Grid()
print([g[i, i + 1] for i in range(4)], kept)
