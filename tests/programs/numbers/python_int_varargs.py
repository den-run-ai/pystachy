# pystachy: python-int
# Promoting ints (docs/python-int.md) in the *args tuple of a call, which a function returns or
# keeps (a dict's key, a set's element, a list's item): the copy it keeps holds them, past 64 bits
# and -2**63 too, also in a module that does not opt in (fixed_varargs), as the key of a cache of
# functools, whose keys are such tuples, and as the arguments that a functools.partial keeps.
from functools import cache, partial
from fixed_varargs import fixed_keep, fixed_pack

big = 2 ** 70
low = -(2 ** 63)


def pack(*args):
    return args


def pack_int(*args: int):
    return args


seen: dict[tuple[int, int], int] = {}
elems: set[tuple[int, int]] = set()
kept: list[tuple[int, int]] = []


def note(*key: int) -> bool:
    found = key in seen
    seen[key] = len(seen)
    elems.add(key)
    kept.append(key)
    return found


@cache
def bits(n: int) -> int:
    return n.bit_length()


def mul(a: int, b: int) -> int:
    return a * b


print(pack(big), pack(big, 1, low), pack_int(big, -big), pack(big * 3), pack("a", big))
print(note(big, 1), note(low, 1), note(big, 1), note(big * 2, low), len(seen), sorted(seen))
print(sorted(elems), kept)
print(fixed_pack(big), fixed_pack(1, big + 1), fixed_keep(big), fixed_keep(low, big))
print(bits(big), bits(low), bits(big), bits(-big), bits.cache_info())
p = partial(mul, big)
print(p(2), p(low), partial(mul, low, big)())
