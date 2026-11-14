# pprint's wrapping of strs and bytes: at spaces (also Unicode's), at line ends and in chunks of
# four bytes, at the top level and nested, for several widths.
import pprint

# str wrapping details
s = "one two  three\tfour\nfive " + "six" * 30 + " seven eight nine  "
for w in (5, 12, 20, 33, 80):
    print(pprint.pformat(s, width=w))
    print(pprint.pformat([s, "tail"], width=w))
    print(pprint.pformat({"k": s}, width=w, indent=2))
    print(pprint.pformat((s,), width=w))
print(pprint.pformat("\n\n", width=1), pprint.pformat(" ", width=1), pprint.pformat("x\n", width=1))
print(pprint.pformat("  lead and trail  ", width=6))
print(pprint.pformat("a\rb\x0bc\x0cd\x1ce\x85f", width=4))
b = bytes(range(40, 80))
for w in (1, 9, 20, 41):
    print(pprint.pformat(b, width=w))
    print(pprint.pformat([b], width=w))
    print(pprint.pformat({"k": b}, width=w))
    print(pprint.pformat((b, b"t"), width=w, compact=True))
