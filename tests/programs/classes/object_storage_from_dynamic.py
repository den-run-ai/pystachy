# pystachy: dynamic-any
# a module that opts in to dynamic Any reads and stores the values of object of a module that does
# not: it prints, compares and narrows them as that module does, gives its Any values to object
# parameters and storage, and a value of object to an Any variable, whose operations are Any's
from typing import Any

import objstore


def main() -> None:
    print(objstore.get(0), objstore.get(1), objstore.get(2), objstore.STORE)
    x = objstore.get(3)
    print(x, x == objstore.STORE[3], x is objstore.STORE[3], objstore.kind(x))
    objstore.put(5)
    objstore.put("six")
    print(objstore.STORE, [objstore.kind(v) for v in objstore.STORE])
    a: Any = 7
    objstore.put(a)
    print(objstore.kind(objstore.get(6)), objstore.STORE[-1] == 7, objstore.STORE[-1] is a)
    y: object = objstore.get(0)
    if isinstance(y, int):
        print(y * 10)
    z: Any = objstore.get(1)
    print(z, z == "two", str(z).upper(), z + "!")
    w: Any = objstore.get(2)
    print(w is None, w == None)
    held: object = a
    print(held, held == 7, held is a, type(held).__name__)


main()
