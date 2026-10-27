# pystachy: python-int
# MicroPython's tests/basics/builtin_hash_intbig.py at commit a39e77f08d1d, unchanged after this header
# (MIT License, Copyright (c) 2013-2026 Damien P. George; see THIRD_PARTY_NOTICES and
# tests/upstream/micropython.md).
# test builtin hash function

print({1 << 66:1}) # hash big int
print({-(1 << 66):2}) # hash negative big int

# __hash__ returning a large number should be truncated
class F:
    def __hash__(self):
        return 1 << 70 | 1
print(hash(F()) != 0)

# this had a particular error with internal integer arithmetic of hash function
print(hash(6699999999999999999999999999999999999999999999999999999999999999999999) != 0)
