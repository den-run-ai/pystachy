# pow(a, b, m) of 64-bit ints: the products of two values below |m| take 128 bits, and |m| itself
# is 2**63 for the smallest int. A negative exponent takes the power of the inverse, which exists
# where a and m share no factor. The operands are made at run time, so that nothing is folded.
seed = 99


def rnd() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed


LO = -9223372036854775807 - 1
HI = 9223372036854775807
EDGES = [LO, LO + 1, LO + 2, -4611686018427387904, -3, -2, -1, 0, 1, 2, 3, 4611686018427387904, HI - 2, HI - 1, HI,
         1000000007, -1000000007, 4294967296, -4294967296, 4294967295, 2305843009213693951, -2305843009213693951]


def num() -> int:
    k = rnd() % 5
    if k == 0:
        return EDGES[rnd() % len(EDGES)]
    v = (rnd() * 2147483648 + rnd()) * 2 + rnd() % 2
    if k == 1:
        v = v % (1 << (1 + rnd() % 62))
    return v if rnd() % 2 == 0 else -v - 1


def power(a: int, b: int, m: int) -> str:
    try:
        return str(pow(a, b, m))
    except ValueError as e:
        return "ValueError: " + str(e)


h = 0
kinds = [0, 0, 0]
for i in range(60000):
    a = num()
    b = num() if rnd() % 3 > 0 else rnd() % 11 - 5
    m = num()
    s = power(a, b, m)
    kinds[2 if s.startswith("V") else 1 if b < 0 else 0] += 1
    for c in s:
        h = (h * 131 + ord(c)) % 1000000007
print(h, kinds)
for a in [LO, LO + 1, -7, -1, 0, 1, 7, HI - 1, HI]:
    print(" ".join([power(a, b, m) for b in [LO, -3, -1, 0, 1, 2, HI] for m in [LO, LO + 1, -9, -1, 0, 1, 2, 9, HI - 1, HI]]))
