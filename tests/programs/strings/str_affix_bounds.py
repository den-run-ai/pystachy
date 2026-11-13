# str.startswith() and str.endswith() take the whole str for start 0 and an end at or past its
# length in bytes, without counting the code points of a receiver that no operation has counted
# yet (#1301); every other start and end counts them. The receivers come fresh from split() and
# upper(), and are non-ASCII too: the ends tried are their byte and code-point lengths, between
# them and past them, negative and out of range, and the start 0, past it and negative
big = 9223372036854775807
text = "é中ab🦊 straße ÉCOLE é x\0y  ab"
needles = ["", "é", "é中", "ab🦊", "🦊", "é", "ß", "x\0", "\0y", "ab", "abc", "é中ab🦊!"]
for w in text.split(" "):
    # the defaults first, while nothing has counted w's code points
    print(repr(w), [(w.startswith(p), w.endswith(p)) for p in needles])
    n = len(w.encode())
    m = len(w)
    for start, end in [(0, n), (0, n - 1), (0, n + 1), (0, m), (0, m + 1), (0, big), (0, 0), (0, -1),
                       (0, -big - 1), (1, n), (-1, n), (m, big), (n, big), (-big - 1, big), (big, big)]:
        print(start, end, [(w.startswith(p, start, end), w.endswith(p, start, end)) for p in needles])
# (upper() maps ASCII letters alone: docs/language/compatibility.md)
up = [w.upper() + "é🦊" for w in "lorem ipsum ab".split(" ")]
print([(u.startswith("LOREM"), u.endswith("🦊"), u.endswith("é🦊", 0, big), u.startswith("IPSUMé"), u.endswith("Mé🦊", 0, 7)) for u in up])
# a fresh receiver that only a whole-str test has seen still counts, indexes and searches
for w in "é中🦊 aé b".split(" "):
    print(w.startswith("é"), w.endswith("🦊"), len(w), w[-1:], w.find("🦊"), w.endswith("é", 0, len(w)))
print("".startswith(""), "".endswith("", 0, big), "".startswith("", 1), "".endswith("x"), "é".startswith("", 0, 2))
print(("x" + "é中").startswith("xé", 0), ("é中" + "x").endswith("中x", 0, 6), ("é中" + "x").endswith("中x", 0, 2))
print(("ab" * 3).startswith(("x", "ba"), 0, big), ("é" * 3).endswith(("x", "éé")), ("é" * 3).endswith(("éé",), 0, 3))
