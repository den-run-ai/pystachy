# Unicode 15.1 classification uses code points and keeps the three number properties distinct.
def show(s: str) -> None:
    print(repr(s), s.isalpha(), s.isalnum(), s.isdecimal(), s.isdigit(), s.isnumeric())


for s in ["", "abcXYZ", "123", "a1", "_", " ", "A\x00B", "é", "界", "Привет", "العربية", "Ελληνικά",
          "עברית", "한글", "न", "नमस्ते", "e\u0301", "\u0345", "\u02b0", "©", "ª", "«", "²", "½", "Ⅳ", "四",
          "٠١٢", "१२३", "１２３", "𝟘𝟙", "\U000104a0", "\U0001e4f0", "\U0001d2c0", "Ⓐ", "①", "\u200b",
          "\U00010000", "\U00010400", "\U00020000", "\U0002ebf0", "\U0002ee5d", "\U0002ee5e", "😀", "\ufffe",
          "\ud800", "\udfff", "\U0010ffff", "a²", "9²", "²٩", "四9", "éa", "a界z", "é\u0301", "²!", "Ⅳa"]:
    show(s)

# The UTF-8 slow path may enter after a long ASCII prefix, then return to ASCII.
for s in ["a" * 4096 + "界" + "a" * 4096, "1" * 4096 + "²" + "1" * 4096, "1" * 4096 + "٩" + "1" * 4096,
          "a" * 4096 + "\u0301", "é" * 32 + "!", "٩" * 32 + "x"]:
    print(len(s), s.isalpha(), s.isalnum(), s.isdecimal(), s.isdigit(), s.isnumeric())

# Bound methods use the same classification; bytes deliberately remain ASCII-only.
s = "界"
alpha = s.isalpha
number = s.isnumeric
print(alpha(), number())
for b in [b"", b"aZ", b"a1", b"12", b"_", b"\x00", b"\xaa", b"\xb2", b"\xe9", b"\xff", b"\xc3\xa9", b"\xd9\xa1"]:
    print(b, b.isalpha(), b.isalnum(), b.isdigit())
