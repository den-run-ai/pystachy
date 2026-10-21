# Empty results stay open through direct forwarding calls. Each call's expected
# type owns the layout; forwarding must not change a shared callee specialization.
def empty(n):
    return []


def mapping(n):
    return {}


def flags(n):
    return set()


def forward(n):
    return empty(n)


def forward_again(n):
    return forward(n)


def forward_mapping(n):
    return mapping(n)


def forward_flags(n):
    return flags(n)


def several_returns(flag):
    if flag:
        return mapping(1)
    return forward_mapping(1)


ints: list[int] = forward_again(1)
words: list[str] = forward_again(1)
ints.append(3)
words.append("word")
print(ints, words, forward_again(1))

names: dict[str, int] = forward_mapping(1)
keyed: dict[tuple[str, int], str] = forward_mapping(1)
names["name"] = 4
keyed["key", 2] = "value"
print(names, keyed, keyed["key", 2], forward_mapping(1))
several: dict[str, int] = several_returns(False)
several["branches"] = 5
print(several, several_returns(True))

strings: set[str] = forward_flags(1)
tuples: set[tuple[str, int]] = forward_flags(1)
strings.add("word")
tuples.add(("key", 2))
print("word" in strings, ("key", 2) in tuples, len(forward_flags(1)))


# These wrappers share the same empty callee. Their concrete return branches
# determine different key layouts, including the earlier empty-return branch.
def names_or_empty(flag):
    if flag:
        return mapping(1)
    return {"filled": 7}


def tuples_or_empty(flag):
    if flag:
        return mapping(1)
    return {("filled", 1): 8}


def flags_or_empty(flag):
    if flag:
        return flags(1)
    return {("filled", 1)}


one = names_or_empty(True)
two = tuples_or_empty(True)
three = flags_or_empty(True)
one["empty"] = 9
two["empty", 2] = 10
three.add(("empty", 2))
print(one, names_or_empty(False), two, tuples_or_empty(False))
print(("empty", 2) in three, ("filled", 1) in flags_or_empty(False))


# Forwarding preserves expected contexts in annotated returns and union callers.
def annotated(n) -> list[str]:
    return forward_again(n)


def optional(n):
    return forward_mapping(n)


result: list[str] = annotated(1)
result.append("return")
value: dict[str, int] | int = optional(1)
print(result, value)
