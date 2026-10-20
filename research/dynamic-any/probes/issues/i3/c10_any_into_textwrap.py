# pystachy: dynamic-any
import textwrap
from typing import Any


def show(s: Any) -> None:
    print(textwrap.wrap(s, 12))


show("the quick brown fox jumps over the lazy dog")
