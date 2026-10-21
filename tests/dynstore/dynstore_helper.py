# pystachy: dynamic-any
# For tests/programs/inference/dynany_store_import.py: a function declared -> Any in a module that
# opts in, into whose result the importing module stores displays
from typing import Any

cont: Any = {}


def get() -> Any:
    return cont
