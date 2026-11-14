"""Lists, dicts and sets whose arrays the collector does not scan (ints, floats, bools) beside
those it must (strs, objects, tuples): each value reaches only uses its arrays allow."""


class Cell:
    def __init__(self, label: str) -> None:
        self.label = label


def numbers(n: int) -> list[int]:
    found = []
    for i in range(n):
        found.append(i * i)
    return found


def labels(n: int) -> list[str]:
    found = []
    for i in range(n):
        found.append(str(i))
    return found


def counts(words: list[str]) -> dict[str, int]:
    table: dict[str, int] = {}
    for word in words:
        table[word] = table.get(word, 0) + 1
    return table


def owners(cells: list[Cell]) -> dict[int, Cell]:
    return {index: cell for index, cell in enumerate(cells)}


def seen(values: list[int]) -> set[int]:
    return set(values)


def pairs(values: list[int]) -> set[tuple[int, int]]:
    return {(value, value + 1) for value in values}


def distinct(words: list[str]) -> int:
    # (dicts and sets that only runtime functions hold: no typed use checks them, their writes do)
    return len({word: word.upper() for word in words}) + len({word.lower() for word in words}) \
        + len(set(words)) + len(dict.fromkeys(words, 0))


def enqueue(word: str) -> None:
    # (queue's store below views it as list[?], this load as list[str]: every view's type holds)
    queue.append(word)


def shouted(words: list[str]) -> list[str]:
    out = list(words)
    for i in range(len(out)):
        out[i] = out[i] + "!"
    return out


def bumped(values: list[int]) -> list[int]:
    out = list(values)
    for i in range(len(out)):
        out[i] = out[i] + 1
    return out


def rows(n: int):
    # (a generator of lists of ints, atomic: each suspension yields its generator's yield type)
    row = []
    for i in range(n):
        row.append(i)
        yield list(row)


def split_all(texts: list[str]):
    for text in texts:
        yield text.split()


def fresh():
    # (a template's empty result, open until its caller types it: made scanned, as pys_list_new is)
    return []


queue = []
spare = []  # (every view of spare is open: what its stores hold is inferred, then checked)
for word in ("x", "y"):
    enqueue(word)
    spare.append(word * 2)
later: list[str] = fresh()
later.append("z")
squares = numbers(5)
names = labels(3)
table = counts(names + ["1"])
cells = owners([Cell("a"), Cell("b")])
floats = [0.5, 1.5] + [2.5]
copied = squares[1:] + squares[:1]
grid = [sum(row) for row in rows(4)]
pieces = [piece for split in split_all(["a b", "c"]) for piece in split]
print(sum(squares), names, sorted(table.items()), cells[1].label, sorted(seen(copied)), len(pairs(squares)), floats)
print(sorted(table.keys()), sorted(table.values()), list(seen([3, 1, 2])), distinct(names + ["0", "A", "a"]), queue, len(spare), later, shouted(names), bumped(squares))
print(grid, pieces)
