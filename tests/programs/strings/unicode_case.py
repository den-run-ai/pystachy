# str's case methods map and test every character as CPython does (Unicode 15.1), not ASCII
# letters alone: mappings to one, two or three characters, of other lengths in bytes, and the
# characters that have a case but no mapping (#120).
def show(s: str) -> None:
    print(repr(s), repr(s.upper()), repr(s.lower()), repr(s.casefold()), repr(s.title()),
          repr(s.capitalize()), repr(s.swapcase()), s.isupper(), s.islower(), s.istitle())


for s in ["", "abcXYZ", "a1 b2", "é", "É", "éCOLE élémentaire", "ÉCOLE ÉLÉMENTAIRE", "Привет мир", "ПРИВЕТ",
          "Ελληνικά", "Ձայն", "ქართული", "ᲥᲐᲠᲗᲣᲚᲘ", "Ꭰꭰ", "\U00010400\U00010428", "\U0001e900\U0001e922",
          "ß", "ẞ", "straße", "STRASSE", "ŉ", "ǰ", "ΐ", "ΰ", "և", "ﬀ", "ﬁ", "ﬃ", "ﬆ", "ᾈ", "ᾳ", "ᾼ", "ῷ",
          "İ", "ı", "İstanbul", "ISTANBUL", "ſ", "K", "Å", "Ω", "Ⱥ", "ⱥ", "Ȿ", "ɐ", "ꞵ", "ꭓ",
          "Ǆ", "ǅ", "ǆ", "ǆungla", "Ǆungla", "ǅungla", "ǅǅ", "ǈ", "ǋ", "ǲ",
          "ª", "º", "ʰ", "ͅ", "Ⓐ", "ⓐ", "Ⅳ", "ⅳ", "ǂ", "ƻ",
          "界", "日本語", "123", "٠١٢", "😀", "é", "É", "́", "­", "​",
          "\ud800", "\udfff", "\U0010ffff", "\x00", "a\x00B", "a界Z", "É界é", "x²", "ça va", "ÇA VA", "Ça Va",
          "they're bill's friends", "o'neil d'été", "x·y", "ß.ß", "ǆ ǆ", "éa Éa aé aÉ", "1é 1É", "_é"]:
    show(s)

# Results of other sizes than their strs, in characters and in bytes; the paths for a str that
# is not ASCII start anywhere in it.
for s in ["a" * 4096 + "é" + "B" * 4096, "B" * 4095 + "É", "ß" * 5000, "ΐ" * 4096, "ﬃ" * 3000, "ı" * 4096,
          "Ⱥ" * 4096, "ⱥ" * 4096, "İ" * 4096, "ǅ" * 2048, "é" * 31 + "!", "a" * 63 + "ß" + "a" * 64]:
    for r in [s.upper(), s.lower(), s.casefold(), s.title(), s.capitalize(), s.swapcase()]:
        total = 0
        for c in r:
            total += ord(c)
        print(len(r), total, repr(r[:2]), repr(r[-2:]))
    print(len(s), s.isupper(), s.islower(), s.istitle())

# Bound methods map the same way; bytes deliberately remain ASCII-only.
s = "straße"
up = s.upper
low = "ÉCOLE".lower
fold = s.casefold
print(up(), low(), fold(), up() == "STRASSE", low() == "école", fold() == "strasse")
for b in [b"", b"aZ", b"\xc3\xa9cole", b"\xc3\x89COLE", b"\xdf", b"\xe9 \xc9", b"\xff"]:
    print(b, b.upper(), b.lower(), b.swapcase(), b.capitalize(), b.isupper(), b.islower())
