# Case mapping and Unicode class answers are remembered by a code point's low bits. Interleave code
# points that share them (U+0100/U+0200/U+0300/U+1E00 share a low byte; U+0410/U+0450 and
# U+0430/U+0470 share six low bits) so that each answer replaces another's, and check that every
# answer stays the code point's own, case-insensitively and in Unicode classes, repeated and mixed.
import re

COLLIDING = "\u0100\u0200\u0300\u1e00\u0101\u0201\u0301\u1e01\u0410\u0450\u0430\u0470\u00c9\u01c9\u03a3\u03c3\u212a\u017f"
TEXTS = [COLLIDING * 3, COLLIDING[::-1] * 2 + "abc", "".join([COLLIDING[i::3] for i in range(3)]) * 2,
         "x" + COLLIDING[:5] + "y" + COLLIDING[5:] + "z"]
for pattern, flags in [(r"[\u0100-\u017f\u0410-\u042f]+", re.I), (r"[\u0100\u0200\u1e00\u0450]+", re.I),
                       (r"\w+", 0), (r"[^\W\d]+", re.I), (r"(?i:\u0101\u0201)", 0), (r"(?i)[\u01c4-\u01cc]+", 0),
                       (r"[\u0430-\u044f]+", re.I), (r"(?i)\u03c3+", 0), (r"(?i)[k\u017f]+", 0),
                       (r"[\u0100\u0300\u0450\u0470]", 0)]:
    rx = re.compile(pattern, flags)
    print(pattern, int(flags))
    for t in TEXTS:
        print(" ", [(m.start(), m.end()) for m in rx.finditer(t)], rx.sub("-", t).count("-"))
    print(" ", [rx.fullmatch(c) is not None for c in COLLIDING])
