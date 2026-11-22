# pystachy: dynamic-any
# in a program whose values of object hold Any values, a list or a dict of typed items, which no Any
# value can hold, is only the value of object that holds it as itself: `is` and `is not` from
# either side compile and compare the objects, as without Any values
# (object_storage_dynamic_identity.py: the objects that Any values hold)
from typing import Any


def main() -> None:
    d = {"a": 1}
    xs = [1, 2]
    a: Any = 5
    held: object = a
    od: object = d
    oxs: object = xs
    print(od is d, d is od, held is d, d is held, oxs is xs, held is xs, od is xs)
    print(od is not d, held is not d, xs is not oxs, xs is not held)


main()
