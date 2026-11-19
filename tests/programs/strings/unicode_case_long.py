# str's case methods on strs of 16 bytes and more, which take other loops than short ones: the
# ASCII letters are mapped sixteen bytes at a time, and the characters that are not ASCII are
# then mapped in place where a mapping keeps its character's bytes, else the str is mapped anew
def show(s: str) -> None:
    print(ascii(s.lower()), ascii(s.upper()), ascii(s.swapcase()))
    print(ascii(s.casefold()), ascii(s.capitalize()), ascii(s.title()))
    print(s.islower(), s.isupper(), s.istitle(), len(s))


# the length where the loops change, ASCII and not, and a letter at each end
for n in [14, 15, 16, 17, 31, 32, 33]:
    show("aB" * (n // 2) + "z" * (n % 2))
    show("é" + "Qx" * (n // 2 - 1) + "Z" * (n % 2))
    show("Qx" * (n // 2 - 1) + "Z" * (n % 2) + "É")
    show("@[`{" * (n // 4) + "~" * (n % 4))

texts = [
    # two-byte characters: unchanged, changed, and a str that begins with ASCII
    "съешь же ещё этих мягких французских булок",
    "СЪЕШЬ ЖЕ ЕЩЁ ЭТИХ МЯГКИХ ФРАНЦУЗСКИХ БУЛОК",
    "Съешь Же Ещё Этих Мягких Французских Булок",
    "the Quick brown ΦΟΞ jumps over the lazy δογ",
    "Élan vital à l'école élémentaire où ça coûte",
    # three- and four-byte characters, with and without case
    "天地玄黃宇宙洪荒日月盈昃辰宿列張",
    "ᾳ ᾼ ἀἈ ⓐⒶ ａＡ ꭰᎠ ეᲔ Ა ᏸᏰ 𐐀𐐨 𞤀𞤢 😀 ქართული",
    "Ａｂｃ ＤＥＦ ｇｈｉ ａａａａａａａａ",
    "𝓐𝓑𝓒 𐐀𐐁𐐂 𐐨𐐩𐐪 𞤀𞤁 𞤢𞤣 plain ascii",
    # mappings that keep their character's bytes with two code points, and those that do not
    "straße und gruß und fuß, GROSS",
    "İstanbul'da ıspanak, İİİ ııı III iii",
    "ŉ ǰ ΐ ΰ և ẖ ẗ ẘ ẙ ẚ ﬀ ﬁ ﬂ ﬃ ﬄ ﬅ ﬆ ﬓ",
    "ǅ ǆ Ǆ ǈ ǉ Ǉ ǋ ǌ Ǌ ǲ ǳ Ǳ in a long str",
    "Ⱥ ⱥ Ɫ ɫ K Å Ω ſ ı ẞ ß µ ς ϐ ϑ ϕ ϖ ϰ ϱ ϵ \u0345",
    # a capital sigma by its context, far from the ends
    "ΟΔΟΣ ΚΑΙ ΟΔΟΣ. ΌΣΟΣ ΣΟΦΟΣ: Σ, ΑΣ; ΑΣ'Σ ΑΣ\u0301 Σ\u0301Α",
    "aΣ bΣ. Σ ΣΣ ΣΣΣ aΣb Σa \u0345Σ a\u0345Σ a.Σ a'Σ",
    # ASCII first and one character that is not, at each place
    "É" + "x" * 20, "x" * 20 + "É", "x" * 10 + "É" + "X" * 10, "x" * 15 + "é", "X" * 14 + "É",
    "ß" + "a" * 16, "a" * 16 + "ß", "a" * 8 + "İ" + "a" * 8, "ﬁ" + "A" * 16,
]
for t in texts:
    show(t)
    show(t + " " + t)

# every ASCII character, and every byte of a bytes, through the loops of long strs and bytes
every = "".join([chr(i) for i in range(128)])
show(every)
show(every[::-1])
data = bytes(range(256))
print(data.lower())
print(data.upper())
print(data.swapcase())
print((data + data).lower() == data.lower() + data.lower(), data.islower(), data.isupper(), data[65:91].isupper())
