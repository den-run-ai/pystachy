# str's classification predicates and repr() on characters of two, three and four bytes, alone
# and in long strs: each is read without a search, and repr() copies a run of printable
# characters at once
def tests(s: str) -> None:
    print(ascii(s), s.isalpha(), s.isalnum(), s.isdecimal(), s.isdigit(), s.isnumeric(), s.isspace())


for s in ["é", "ж", "ي", "ﬁ", "天", "ქ", "ⓐ", "𐐀", "𞤢", "😀", "٣", "३", "๓", "０", "𝟘", "²", "½", "Ⅷ", "〇", "㊀",
          "\u00a0", "\u2003", "\u3000", "\u200b", "\u0301", "\u0345", "\ud7ff", "\ue000", "�", "\U0001f600",
          "\U000e0001", "\U000e0100", "\U0010ffff", "\x7f", "\x80", "\xad"]:
    tests(s)
    tests(s * 9)
    tests("a" + s)
    tests(s + "1")
for s in ["съешьжеещёэтихмягкихфранцузскихбулок", "天地玄黃宇宙洪荒日月盈昃辰宿列張寒來暑往", "Élanvitalàlécoleélémentaire",
          "٠١٢٣٤٥٦٧٨٩०१२३४५६७८९０１２３", "abc١٢٣def४५६ghi７８９", "²³¹½¼¾ⅠⅡⅢ", "𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡", "𐐀𐐁𐐂𐐨𐐩𐐪𞤀𞤁𞤢𞤣"]:
    tests(s)
    tests(s + " ")
    tests(s + "\u0301")

for s in ["съешь же ещё", "天地玄黃 宇宙洪荒", "Élan vital à l'école", "😀 𐐀𐐨 𞤀𞤢", "tab\there", 'both \' and "',
          "é\u200bé", "天\u3000地", "a\u00a0b\u00adc", "\u0301\u0345", "x\ue000y\uf8ffz", "ж\u2028ж\u2029ж",
          "\ud7ff�\uffff", "\U0001f600\U000e0001\U000e0100\U0010ffff", "é\\ж'天\"😀", "\x7f\x80\x9f\xa0\xa1",
          "ΟΔΟΣ" * 9 + "\u200b" + "οδος" * 9, "天" * 40 + "\x00" + "地" * 40, "é" * 15, "é" * 16, "é" * 17]:
    print(repr(s))
    print(repr([s, s]), str({s: s}))
    print(ascii(s), len(repr(s)))
    print(f"{s!r:>10}|{s!a}")
