# error: cannot iterate over int
# lib/random's choices() takes k as a keyword: for an int weights, CPython raises TypeError, The
# number of choices must be a keyword argument: k=3, where iterating it fails; Pystachy compiles no
# iteration of an int (lib/README.md)
import random

random.seed(1)
print(random.choices(["a", "b"], 3))
