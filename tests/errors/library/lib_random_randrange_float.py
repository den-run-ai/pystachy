# error: 'float' has no method '__index__'
# lib/random's randrange() takes ints (and bools) through operator.index(): CPython raises
# TypeError, 'float' object cannot be interpreted as an integer (lib/README.md)
import random

random.seed(1)
print(random.randrange(10.0))
