# error: a nested sequence or class pattern in a pattern of a list subject is not supported: CPython takes the items before matching any; capture the item and match it in a nested match, or use *_
# a list subject's items are taken before any subpattern runs; a nested pattern would read its item
# after the earlier subpatterns' comparisons, which may change the list
def first_pair(value: list[list[int]]) -> int:
    match value:
        case [[a, b], c]:
            return a + b + len(c)
    return 0


print(first_pair([[1, 2], [3]]))
