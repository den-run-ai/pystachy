# error: a starred capture of no items of a fixed tuple whose items have no common type has no item type; use *_ there
# *rest of a fixed tuple whose other subpatterns take every item is an empty list, of the type the
# tuple's items have in common: one of an int and a str has none
def pair(value: tuple[int, str]) -> int:
    match value:
        case (first, _, *rest):
            return first + len(rest)
    return -1


print(pair((3, "x")))
