# error: generic_pep695_paramspec.py:5: error: ParamSpec type parameters (**P) are not supported
from typing import Callable


class Wrap[**P]:
    def __init__(self, f: Callable[P, int]) -> None:
        self.f = f


print("never")
