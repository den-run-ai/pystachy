def callc(n: int) -> int:
    if n < 0:
        raise ValueError("neg")
    return n


def tryapply(n: int) -> int:
    try:
        return callc(n)
    except ValueError:
        return -1


def check(n: int) -> int:
    if n < 0:
        raise ValueError("negative")
    return n * 2
