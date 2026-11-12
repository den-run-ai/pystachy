# error: complex literal patterns are not supported
def zero(value: int) -> bool:
    match value:
        case 0 | 0j:
            return True
    return False


print(zero(0))
