# error: Random.getrandbits() got some positional-only arguments passed as keyword arguments: 'k'
# lib/random's getrandbits() is _random.Random's, whose k is positional-only: CPython raises
# TypeError, Random.getrandbits() takes no keyword arguments
import random

random.seed(1)
print(random.getrandbits(k=8))
