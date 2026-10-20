# str * n: a one-byte string (filled by memset), longer ones (the copied prefix doubles),
# counts that are not powers of two, UTF-8, empty strings, counts <= 0 and the overflow check


def check(unit: str, n: int) -> str:
    s = unit * n
    k = len(unit)
    if len(s) != k * n:
        return "bad length " + str(len(s))
    for i in range(len(s)):
        if s[i] != unit[i % k]:
            return "bad at " + str(i)
    return "ok " + str(len(s))


for unit in ["y", "ab", "abc", "abcdefg", "0123456789" * 10]:
    for n in [1, 2, 3, 4, 5, 7, 8, 9, 15, 16, 17, 100, 1000, 1023, 1024, 1025]:
        print(len(unit), n, check(unit, n))

s = "y" * 100000
print(len(s), s.count("y"), s[:3], s[-3:])
t = "ab" * 50000
print(len(t), t.count("ab"), t.count("ba"), t[:5], t[-5:])
u = "xyz" * 333333
print(len(u), u.count("xyz"), u[99999:100005], u.endswith("xyz"), u.startswith("xyzx"))

print("é" * 5, "日本" * 3, "a€" * 4, "\x00" * 3 == "\x00\x00\x00", ("\x00" * 3).count("\x00"))
print(repr("" * 5), repr("" * 0), repr("" * -3), repr("" * 9223372036854775807))
print(repr("abc" * 0), repr("abc" * -1), repr("x" * -9223372036854775807), repr("xy" * -9223372036854775807))
print(3 * "ab", repr(-2 * "ab"), repr(0 * "q"), 1 * "one")
w = "ab"
w *= 3
print(w)
w *= 0
print(repr(w))


def rep(x: str, n: int) -> str:
    return x * n


for n in [4611686018427387904, 9223372036854775807]:
    try:
        print(len(rep("ab", n)))
    except OverflowError as e:
        print("OverflowError:", e)
try:
    print(len(rep("abcdefgh", 1152921504606846976)))
except OverflowError as e:
    print("OverflowError:", e)
