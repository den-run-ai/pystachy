# pystachy: dynamic-any
# an Any parameter narrowed by isinstance before a typed library call
import textwrap
from typing import Any


def show(s: Any) -> None:
    if isinstance(s, str):
        print(textwrap.wrap(s, 12))


show("the quick brown fox jumps over the lazy dog")
