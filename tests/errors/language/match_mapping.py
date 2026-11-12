# error: mapping patterns are not supported
# (the statement is rejected at its first pattern outside the bounded lowering: the second case)
def lookup(value: dict[str, int]) -> int:
    match value:
        case None:
            return 0
        case {"a": number}:
            return number
    return -1


print(lookup({"a": 1}))
