# lib/random.py: CPython 3.13's random with its marked edits (lib/README.md), whose generator is
# lib/_pyrandom.py, the Mersenne Twister of _random (Modules/_randommodule.c), against CPython's:
# int seeds (0, negative, 32-bit boundaries, 63-bit and -2**63, bools, seeds from a linear
# congruential generator), float seeds (through their hash), random() over many regenerations of
# the 624-word state, getrandbits() from 0 to 63 bits, getstate()/setstate() and their errors,
# unseeded generators, the module's functions on its hidden instance, and a Random in functions,
# methods, closures, templates and fields
import math
import random
from random import Random


def lcg(x: int) -> int:
    return x * 48271 % 2147483647


seeds = [0, 1, -1, 2, 42, 1000, 2**31 - 1, 2**31, 2**32 - 1, 2**32, 2**32 + 1, -2**32, 2**33 - 7,
         12345678901234, -98765432109876, 2**62, 2**62 + 12345, 9223372036854775807,
         -9223372036854775807, -9223372036854775807 - 1]
x = 7
for i in range(24):
    # 63-bit seeds of two 31-bit draws, some shifted down to fewer words, some negative
    hi = lcg(x)
    x = lcg(hi)
    s = ((hi << 32) | x) >> (i * 3 % 40)
    seeds.append(-s if i % 3 == 0 else s)

print("first draws of int seeds")
for s in seeds:
    r = Random(s)
    print(s, r.random(), r.random(), r.getrandbits(32), r.getrandbits(63))

print("bool seeds")
for b in [True, False]:
    r = Random(b)
    print(b, r.random(), Random(int(b)).random())
    r.seed(b)
    print(r.random())

print("float seeds")
for f in [0.0, -0.0, 1.0, -1.0, 1.5, -2.25, 3.0, 0.1, 1e-300, 5e-324, 1e20, 2.0**61, 2.0**62,
          -(2.0**63), 1e300, -1.7976931348623157e308, math.inf, -math.inf, 123456.789]:
    r = Random(f)
    print(f, r.random(), r.getrandbits(17))
# a float equal to an int has that int's hash, and seeds as that int does
print(Random(7.0).random() == Random(7).random(),
      Random(2.0**40).random() == Random(2**40).random())

print("long sequences")
r = Random(2024)
total = 0.0
checksum = 0
for i in range(5000):
    v = r.random()
    total += v
    if i % 997 == 0:
        print(i, v)
for i in range(3000):
    checksum ^= r.getrandbits(32) << (i % 31)
print(total, checksum, r.random())
values = [r.random() for i in range(1300)]
print(math.fsum(values), min(values), max(values), values[623], values[624], values[1247])

print("getrandbits")
r = Random(99)
print([r.getrandbits(k) for k in range(64)])
print([r.getrandbits(k).bit_length() <= k for k in [0, 1, 31, 32, 33, 62, 63]])
for k in [1, 8, 32, 33, 63]:
    r.seed(k)
    print(k, [r.getrandbits(k) for i in range(6)])
try:
    r.getrandbits(-1)
except ValueError as e:
    print("ValueError:", e)

print("getstate and setstate")
r = Random(5)
r.random()
state = r.getstate()
print(state[0], len(state[1]), state[1][0], state[1][623], state[1][624], state[2])
a = [r.random() for i in range(5)]
r.setstate(state)
print(a == [r.random() for i in range(5)])
g = r.gauss()
state = r.getstate()
print(state[2] is not None, r.gauss() != g)
r.setstate(state)
h = r.gauss()
r.setstate(state)
print(h == r.gauss(), state[2] == h)
r.seed(5)
print(r.getstate()[2] is None, r.getstate()[1][624])
# the inner state of version 2 was saved as signed ints, which setstate() takes modulo 2**32
inner = list(Random(8).getstate()[1])
for i in range(0, 624, 7):
    if inner[i] >= 2**31:
        inner[i] -= 2**32
r.setstate((2, tuple(inner), None))
print(r.random() == Random(8).random())
# a word of more than 32 bits keeps its low 32 bits, as C's (uint32_t) cast
inner = list(Random(9).getstate()[1])
inner[100] += 5 << 32
r.setstate((3, tuple(inner), 0.25))
print(r.random() == Random(9).random(), r.gauss())
for bad_state in [(4, Random(1).getstate()[1], None), (1, Random(1).getstate()[1], None)]:
    try:
        r.setstate(bad_state)
    except ValueError as e:
        print("ValueError:", e)
for bad_inner in [tuple([1, 2, 3]), tuple(list(Random(1).getstate()[1]) + [0])]:
    try:
        r.setstate((3, bad_inner, None))
    except ValueError as e:
        print("ValueError:", e)
for index in [-1, 625, 624, 0]:
    inner = list(Random(1).getstate()[1])
    inner[624] = index
    try:
        r.setstate((3, tuple(inner), None))
        print(index, r.random())
    except ValueError as e:
        print(index, "ValueError:", e)
inner = list(Random(1).getstate()[1])
inner[3] = -1
try:
    r.setstate((3, tuple(inner), None))
except OverflowError as e:
    print("OverflowError:", e)

print("unseeded generators")
fresh = Random()
fresh_none = Random(None)
reseeded = Random(1)
reseeded.seed()
reseeded.seed(None)
print(all([0.0 <= gen.random() < 1.0 for gen in [fresh, fresh_none, reseeded]]),
      fresh.getstate()[1][624], reseeded.getstate()[2])

print("module functions")
random.seed(12345)
print(random.random(), random.getrandbits(40), random.random())
saved = random.getstate()
first = random.random()
random.setstate(saved)
print(first == random.random())
random.seed(12345, version=1)
print(random.random())
random.seed(-12345, 2)
print(random.random() == Random(12345).random())
random.seed(a=7)
draw = random.random
print(draw(), draw())
random.seed()
print(0.0 <= random.random() < 1.0)


def from_generator(gen: Random, n: int) -> list[float]:
    return [gen.random() for i in range(n)]


def draws(gen, n):
    # a template on the generator's type
    return [gen.getrandbits(8) for i in range(n)]


class Dice:
    def __init__(self, seed: int) -> None:
        self.gen = Random(seed)
        self.rolls: list[int] = []

    def roll(self) -> int:
        value = self.gen.getrandbits(16) % 6 + 1
        self.rolls.append(value)
        return value


def make_counter(seed: int):
    gen = Random(seed)

    def next_value() -> float:
        return gen.random()
    return next_value


print("in functions, methods and closures")
print(from_generator(Random(3), 3), draws(Random(3), 4))
d = Dice(11)
print([d.roll() for i in range(10)], d.rolls == [d.rolls[i] for i in range(10)])
counter = make_counter(3)
print(counter(), counter(), from_generator(Random(3), 2))
bound = Random(4).random
print(bound(), bound())
