# Reads reexpkg.types_' copies of constants while reexpkg.types_ is still being imported
from reexpkg.again import AGAIN
from reexpkg.types_ import ALL_STRATEGY, ANY_STRATEGY, NAME, ON, RATE

DEFAULT = ANY_STRATEGY + ALL_STRATEGY
print("expand", ANY_STRATEGY, ALL_STRATEGY, NAME, ON, RATE, DEFAULT, AGAIN)


def expand(n: int) -> str:
    return NAME * n
