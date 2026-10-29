# Original container/lifetime and immutable-alias regressions. Normal verification
# also runs this with a collection at every allocation in JIT and AOT.
try:
    from mpz import mpz
except ImportError:
    from mpz_oracle import mpz


class Holder:
    def __init__(self, value: mpz) -> None:
        self.value = value


def make_values() -> list[mpz]:
    result: list[mpz] = []
    for i in range(32):
        result.append((mpz(1) << (64 + i)) + i)
    return result


def return_copy(value: mpz) -> mpz:
    return value.copy()


values = make_values()
original = values[7]
alias = original
copy = return_copy(original)
holder = Holder(original)
assert copy == original
lookup: dict[mpz, str] = {}
for value in values:
    lookup[value] = str(value)
unique: set[mpz] = set(values)
assert len(lookup) == 32 and len(unique) == 32
saved = str(original)
changed = original + 1
original += 10
assert str(alias) == saved and str(copy) == saved and str(holder.value) == saved
assert changed == alias + 1 and original == alias + 10
for i in range(80):
    # Create nontrivial limb temporaries after references have crossed fields,
    # returns, typed list items and dictionary keys. The original payloads remain.
    scratch = ((mpz(1) << 192) + i).pow(3)
    assert scratch.bit_length() >= 577
for value in values:
    parsed = mpz(str(value))
    assert lookup[parsed] == str(value)
    assert parsed in unique
assert lookup[copy] == saved and holder.value in unique
# Explicit reinitialization cannot invalidate a key already in a dictionary.
copy.__init__(9)
assert str(copy) == saved and lookup[copy] == saved
values.reverse()
assert values[-1] == mpz("18446744073709551616")
values.sort()
assert values[0] == mpz("18446744073709551616")
assert len(values[:10] + values[10:]) == 32
print("immutable aliases and typed storage", len(values), len(lookup), len(unique))
print(saved, original, changed)
