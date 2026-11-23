# error: a bytes value cannot become an Any value (making the table of bytes as object (for Any)
# pystachy: dynamic-any
# a value of object compared with an Any value becomes one through each stored type's table
# entry, and a bytes value cannot become an Any value (nor can a dict of typed items)
from typing import Any


def main() -> None:
    xs: list[object] = [b"raw", 1]
    a: Any = 1
    print(xs[1] == a)


main()
