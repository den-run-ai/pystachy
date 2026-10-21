# pystachy: dynamic-any
# An int literal as an Any value, the same in two modules (tests/programs/inference/dynany_identity_modules.py)
from typing import Any

big: Any = 1000


def big_again() -> Any:
    return 1000
