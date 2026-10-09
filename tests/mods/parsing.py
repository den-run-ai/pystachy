# a module whose functions raise, and one with a try of its own at the top level

LIMIT = 100
try:
    WIDTH = int("eighty")
except ValueError:
    WIDTH = 80


def number(s: str) -> int:
    n = int(s)
    if n > LIMIT:
        raise OverflowError(f"{n} is above {LIMIT}")
    return n


def safe(s: str) -> int:
    try:
        return number(s)
    except ValueError:
        return -1
