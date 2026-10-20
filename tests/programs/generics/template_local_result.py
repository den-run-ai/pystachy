# Context reaches fresh displays/calls only through a proven straight-line
# assignment chain. Independent contexts retain their own native layouts.
def empty(n):
    return []


def mapping(n):
    return {}


def local_empty(n):
    result = empty(n)
    alias = result
    final = alias
    return final


def local_mapping(n):
    result = mapping(n)
    return result


def local_list(n):
    result = []
    return result


def local_dict(n):
    result = {}
    return result


def local_set(n):
    result = set()
    alias = result
    return alias


words: list[str] = local_empty(1)
numbers: list[int] = local_empty(1)
words.append("word")
numbers.append(3)
print(words, numbers, local_empty(1))

strings: list[str] = local_list(1)
strings.append("fresh")
names: dict[str, int] = local_mapping(1)
keys: dict[tuple[str, int], str] = local_mapping(1)
names["name"] = 4
keys["key", 2] = "value"
direct: dict[tuple[str, int], int] = local_dict(1)
direct["tuple", 3] = 5
print(strings, names, keys, keys["key", 2], direct)

flags: set[tuple[str, int]] = local_set(1)
flags.add(("flag", 4))
print(("flag", 4) in flags, len(flags))


def pair(a, b):
    """Fresh mixed values preserve their original scalar tags."""
    result = [a, b]
    alias = result
    return alias


def pair_wrapper(a, b):
    result = pair(a, b)
    return result


def nested(a, b):
    result = ([a, b], {"values": [a, b]})
    alias = result
    return alias


mixed: list[int | float] = pair(9007199254740993, 2.5)
wider: list[int | float | str] = pair_wrapper(9007199254740993, 2.5)
wider.append("wide")
print(mixed, wider, isinstance(mixed[0], int), mixed[0] == 9007199254740993)
tree: tuple[list[int | float], dict[str, list[int | float]]] = nested(1, 2.5)
print(tree, isinstance(tree[1]["values"][0], int))


class Factory:
    def make(self, n):
        result = local_mapping(n)
        return result


factory = Factory()
bound = factory.make
method: dict[tuple[str, int], int] = bound(1)
method["bound", 5] = 6
print(method)


def consume(value: list[int | float]) -> None:
    print(value)


def annotated(n) -> list[str]:
    return local_empty(n)


consume(pair_wrapper(1, 2.5))
print(annotated(1))
optional: dict[str, int] | int = local_mapping(1)
print(optional)


def scalar_record(n):
    result = (n,)
    alias = result
    return alias


record: tuple[int | str] = scalar_record(9007199254740993)
print(record, isinstance(record[0], int))


# A comparison hint must not choose a layout for an earlier empty child.
# A required result type can still specialize the same local-forwarding body.
def filled(n):
    return [n]


def local_rows(n):
    result = [empty(n), filled(n)]
    alias = result
    return alias


expected: list[list[str]] | float = [["word"]]
print(expected == local_rows(1))
required: list[list[int | str]] = local_rows(1)
required[0].append("first")
required[1].append("second")
print(required, isinstance(required[1][0], int))
