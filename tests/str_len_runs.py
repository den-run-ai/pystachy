# len() of strs whose code-point count is not yet known (made by join): the runtime counts ASCII
# runs a block of bytes at a time and decodes each other character. Characters of one to four
# bytes, and raw bytes, sit at offsets around the block size; indexing and slicing then use the count.
chars = ["a", "\x7f", "é", "€", "\U0001d504", chr(0x80), chr(0xff)]
for n in [0, 1, 31, 32, 33, 63, 64, 65, 100]:
    for c in chars:
        for at in sorted({0, n // 2, n - 1, n} if n else {0}):
            s = "".join(["x" * at, c, "y" * (n - at)])
            print(n, ord(c), at, len(s), s[at] == c, len(s[at:]), s.find(c) == at)

mixed = "".join(["a" * 40, "é" * 3, "b" * 70, "€", "c" * 33, "\U0001d504", "d" * 5])
print(len(mixed), mixed.index("€"), mixed[-6], len(mixed.upper()), len("".join([mixed] * 50)))
big = "".join(["q" * 10000, "é", "r" * 10000])
print(len(big), big[10000] == "é", big.count("r"), len(big[5000:15000]))
print(len("".join(["\ud800", "x" * 40, "\udfff"])), len(" ".join(["word"] * 1000)), len("".join([])))
