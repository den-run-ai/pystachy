import re
from _weakref import ref


class Item:
    def __init__(self, value: int):
        self.value = value


def churn() -> None:
    # Allocation pressure without dereferencing a reference (see lib_weakref_transition.py)
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


def create():
    owners = [Item(i) for i in range(256)]
    others = [Item(i) for i in range(256)]
    return [ref(item) for item in owners], [ref(item) for item in others], owners, others


def observe_and_release(hashed: list[ref[Item]], unhashed: list[ref[Item]], owners: list[Item], others: list[Item]) -> list[int]:
    # Live references compare their referents; only the first cohort is hashed while alive.
    # (CPython reuses one reference per referent, so no two references share one here.)
    print(all(hashed[i] == ref(owners[i]) and not hashed[i] != hashed[i] for i in range(len(hashed))))
    print(all(hashed[i] != hashed[i + 1] and hashed[i] != unhashed[i] for i in range(len(hashed) - 1)))
    hashes = [hash(r) for r in hashed]
    print(all(hashes[i] == hash(owners[i]) for i in range(len(owners))))
    owners.clear()
    others.clear()
    return hashes


hashed, unhashed, owners, others = create()
hashes = observe_and_release(hashed, unhashed, owners, others)
churn()
# A conservative collector may keep a few referents; at least one of each cohort must die.
# A dead reference is equal only to itself, keeps the hash it had and cannot get a first one.
dead = [i for i in range(len(hashed)) if hashed[i]() is None]
gone = [i for i in range(len(unhashed)) if unhashed[i]() is None]
print(len(dead) > 0, len(gone) > 0)
ok = True
for k in range(len(dead)):
    r = hashed[dead[k]]
    ok = ok and r == r and not r != r and hash(r) == hashes[dead[k]]
    ok = ok and re.fullmatch("<weakref at 0x[0-9a-f]+; dead>", repr(r)) is not None
    if k > 0:
        ok = ok and not r == hashed[dead[k - 1]] and r != hashed[dead[k - 1]]
for i in range(len(hashed)):
    if hashed[i]() is not None and len(dead) > 0:
        ok = ok and hashed[i] != hashed[dead[0]]
for i in gone:
    u = unhashed[i]
    ok = ok and u == u and not u == hashed[i]
    try:
        hash(u)
        ok = False
    except TypeError as e:
        ok = ok and str(e) == "weak object has gone away"
print(ok)
for i in range(len(hashed)):
    value = hashed[i]()
    if value is not None:
        assert value.value == i and hash(hashed[i]) == hash(value)
