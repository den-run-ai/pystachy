# Re-exports reexpkg.consts' constants (as mypy's types.py re-exports type_visitor's
# ANY_STRATEGY), then imports reexpkg.expand, which imports this module back
from reexpkg.consts import ALL_STRATEGY, NAME, ON, RATE
from reexpkg.consts import ANY_STRATEGY as ANY_STRATEGY
from reexpkg.expand import expand


def run() -> str:
    return expand(3)
