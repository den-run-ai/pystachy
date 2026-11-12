# error: starred sequence patterns are not supported; use a fixed tuple pattern
def head(value: tuple[int, int, int]) -> int:
    match value:
        case (first, *rest):
            return first
    return -1


print(head((1, 2, 3)))
