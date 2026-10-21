# A slice that covers its whole str, and a strip that strips nothing, give that str itself, as in
# CPython: no copy (#82). Anything shorter is a new str.


def same(label: str, a: str, b: str) -> None:
    print(label, a is b, a == b, len(a))


def bounds(s: str, lo: int, hi: int) -> str:
    return s[lo:hi]


s = "hello, world"
same("s[:]", s[:], s)
same("s[0:]", s[0:], s)
same("s[:len(s)]", s[: len(s)], s)
same("s[-len(s):]", s[-len(s) :], s)
same("s[-100:100]", s[-100:100], s)
same("s[None:None]", s[None:None], s)
same("bounds(s, 0, 12)", bounds(s, 0, 12), s)
same("bounds(s, -99, 99)", bounds(s, -99, 99), s)
same("s[1:]", s[1:], s)
same("s[:-1]", s[:-1], s)
same("s[:11]", s[:11], s)
same("bounds(s, 0, 11)", bounds(s, 0, 11), s)

e = ""
same("e[:]", e[:], e)
same("e[5:]", e[5:], e)
same("e[-5:5]", e[-5:5], e)

made = str(1234567) + "x"  # a str made at run time, not a literal
same("made[:]", made[:], made)
same("made[0:]", made[0:], made)
same("made[:len(made)]", made[: len(made)], made)

texts = ["abc", " abc", "abc ", " abc ", "", " ", "\t\n", "é", " é ", "xyx", "yxy", "a b"]
for t in texts:
    print(repr(t), t.strip() is t, t.lstrip() is t, t.rstrip() is t, t.strip("x") is t, t.lstrip("xy") is t, t.rstrip("y") is t)
    print(" ", repr(t.strip()), repr(t.lstrip()), repr(t.rstrip()), repr(t.strip("x")), repr(t.lstrip("xy")), repr(t.rstrip("y")))

# the str given back is the one kept: building on it makes a new one, and it stays as it was
k = s[:]
k += "!"
print(s, k, s is k)
kept: list[str] = []
for i in range(4):
    kept.append(s.strip())
print(all(x is s for x in kept), len(kept))

# a dict keyed by a str finds it again through the whole slice, whose hash is the same str's
d = {s: 1}
print(d[s[:]], s[:] in d, s[0:] in d)
