# %c of a code point outside range(0x110000) raises OverflowError (chr() raises ValueError)
codes = [0x10FFFF, 0x110000]
for c in codes:
    print("%c" % c == chr(c))
