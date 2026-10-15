# A direct empty result takes its container type at each call. The same argument
# types share a function specialization without fixing all callers' element types.
def empty(n):
    return []


def empty_dict(n):
    return {}


def empty_set(n):
    return set()


ints: list[int] = empty(1)
words: list[str] = empty(1)
floats: list[float] = empty(1)
ints.append(3)
words.append("word")
floats.append(2.5)
print(ints, words, floats, empty(1))

numbers: dict[int, int] = empty_dict(1)
names: dict[str, str] = empty_dict(1)
pairs: dict[tuple[str, int], int] = empty_dict(1)
numbers[3] = 4
names["name"] = "value"
pairs["key", 2] = 5
print(numbers, names, pairs, empty_dict(1))
print(names["name"], pairs["key", 2], "name" in names)

flags: set[str] = empty_set(1)
flags.add("ok")
print("ok" in flags, len(flags), len(empty_set(1)))


def takes(xs: list[str]) -> list[str]:
    xs.append("argument")
    return xs


def result() -> dict[str, int]:
    return empty_dict(1)


print(takes(empty(1)))
returned = result()
returned["return"] = 6
print(returned)


# A later concrete return determines the earlier empty allocation's key kind,
# even when the first call executes the empty branch.
def choose(flag):
    if flag:
        return {}
    return {"filled": 7}


def tuple_keys(flag):
    if flag:
        return {}
    return {("key", 1): 8}


def sets(flag):
    if flag:
        return set()
    return {("key", 1)}


chosen = choose(True)
chosen["empty"] = 9
keyed = tuple_keys(True)
keyed["new", 2] = 10
tuples = sets(True)
tuples.add(("new", 2))
print(chosen, choose(False), keyed, tuple_keys(False))
print(("new", 2) in tuples, ("key", 1) in sets(False))


def multiple(flag):
    if flag:
        return []
    return []


many: list[str] = multiple(True)
many.append("many")
print(many, multiple(False))
