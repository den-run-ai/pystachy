# error: sequence patterns require a tuple or list subject, got list[int] | None
# an optional sequence subject needs narrowing before a sequence pattern
def head(value: list[int] | None) -> int:
    match value:
        case [first, *_]:
            return first
    return -1


print(head([4, 5]), head(None))
