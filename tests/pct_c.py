# "%c" takes one character, or an int in range(0x110000) (OverflowError), with a width.
for s in ["ab", "", "é", "x"]:
    try:
        print(repr("%c" % s), repr("%3c|%-3c|" % (s, s)))
    except TypeError as e:
        print("TypeError", e)
for v in [65, 1114111, 1114112, -1, 2**40]:
    try:
        print(repr("%c" % v), repr("%3c" % v))
    except OverflowError as e:
        print("OverflowError", e)
print(repr("%3c|%-3c|" % (66, "x")), repr("%c" % True))
v = -1
print("%c" % v)
