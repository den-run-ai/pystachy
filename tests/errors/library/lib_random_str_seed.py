# error: expected bool | float | int | None, got str
# lib/random's seeds are ints, floats, bools and None (lib/README.md): a str, bytes or bytearray
# seed takes sha512() of hashlib, and the long int of the text and its digest (CPython's version 2)
import random

random.seed("pystachy")
print(random.random())
