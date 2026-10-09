# error: None/Optional is only supported for class types, str, int, float, bool, list, dict and tuple, not file
from typing import TextIO


def f(fp: TextIO | None) -> None:
    print(fp)
