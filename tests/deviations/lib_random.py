# Documented deviations of lib/random (CPython 3.13's random with marked edits, on lib/_pyrandom's
# Mersenne Twister) from CPython.
import math
import random
from collections import deque
from random import Random

# Pystachy's ints are 64-bit: getrandbits() takes up to 63 bits, and raises OverflowError past
# them before it draws: CPython prints 10499958131665514997, then 0.8474337369372327.
r = Random(1)
try:
    print(r.getrandbits(64))
except OverflowError as e:
    print("OverflowError:", e)
print(r.random())

# A range whose width leaves 64 bits raises OverflowError: CPython prints -2922244813938350433.
try:
    print(Random(2).randrange(-2**62, 2**62))
except OverflowError as e:
    print("OverflowError:", e)

# So does a range whose width fits, where randint()'s b + 1 or randrange()'s width + step leaves
# them: CPython prints 9223372036854775799, then 0.
M = 9223372036854775807
try:
    print(Random(1).randint(M - 10, M))
except OverflowError as e:
    print("OverflowError:", e)
try:
    print(Random(1).randrange(0, M, M))
except OverflowError as e:
    print("OverflowError:", e)

# A NaN seeds as its hash, which is its object's address in CPython (so its draws differ from run
# to run there); a Pystachy float has none, and its hash is 0: CPython prints False.
print(Random(math.nan).random() == Random(0).random())

# sample() takes what isinstance() finds a collections.abc.Sequence: a deque is none in Pystachy,
# and a dict view, a list, is one: CPython prints [1, 3], then raises TypeError for the keys.
try:
    print(Random(1).sample(deque([1, 2, 3]), 2))
except TypeError as e:
    print("TypeError:", e)
try:
    print(Random(1).sample({"a": 1, "b": 2}.keys(), 1))
except TypeError as e:
    print("TypeError:", e)

# SystemRandom, made where os.urandom() imports, is not in __all__: CPython prints True 26.
print("SystemRandom" in random.__all__, len(random.__all__))
