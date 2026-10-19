# A search for alternatives that each begin with literals or classes steps a bit-parallel filter
# of their first n items (n the least count of them, as many as 62 bits hold for all) through the
# subject, and enters the matcher only where an alternative's leading items all match. Alternatives
# of different lengths, more of them than fit, classes with members from U+0080, overlapping
# candidates, matches that end the subject, bounds and every operation, over subjects read in place
# and decoded ones.
import re

many = "|".join(["%c%c%c" % (97 + i % 26, 97 + (i * 7) % 26, 97 + (i * 3) % 26) for i in range(25)])
patterns = ["agggtaaa|tttaccct", "[cgt]gggtaaa|tttaccc[acg]", "abcd|xy", "abc|abd|abe", "aa|ab", "(ab|cd)xyz",
            "[é-ê]x|ab", "(?:foo|ba[rz])+", "x[^a-c]y|[ab]{2}", many, "ab|a", "(?s)a.|bb"]
subjects = ["", "xxagggtaaatttaccctxx", "cgggtaaa tttacccg aagggtaaa", "abcdxyabcexy", "aaab aab ab",
            "abxyz cdxyzab", "éx ab êx èx", chr(0xE9) + "x" + chr(0xEA) + "xab", "foobarbazfoo bar",
            "xdy xay abba", "abc " + many[:20], "a\nbba"]
for pi in range(len(patterns)):
    rx = re.compile(patterns[pi])
    for si in range(len(subjects)):
        s = subjects[si]
        print(pi, si, [m.span() for m in rx.finditer(s)], rx.subn("#", s)[1], len(rx.split(s)),
              [m.span() for m in [rx.search(s, 2), rx.search(s, 0, len(s) - 1), rx.match(s)] if m is not None])
dna = "".join(["acgt"[(i * 7 + i // 3) % 4] for i in range(5000)]) + "agggtaaa"
for p in ["agggtaaa|tttaccct", "[cgt]gggtaaa|tttaccc[acg]", "a[act]ggtaaa|tttacc[agt]t", "ag|ct|ga"]:
    print(p, len(re.findall(p, dna)), len(re.findall(p, dna + "é")), re.compile(p).search(dna, 4990) is not None)

# Characters from U+0080: where no alternative's leading item may match one, its bits are 0 untested;
# else the alternatives it begins come from a memo of 64 slots by its low bits, where \u0410, \u0450,
# \xd0 and \U0001d510 share one, and only the next items of the matches under way are tested.
# Literals, ASCII classes, ranges from U+0080, Unicode categories, negated classes, and CJK
# alternatives over text of more characters than the memo holds, with matches under way.
cyr = "абвгдежзийклмнопрстуфхцчшщъыьэюя"
wide = ["(?:error|warning)", "[a-c]x|[d-f]y", "(?:Аб|ѐв|Ðг)", "[А-Я]б|[ѐ-ё]в", r"\wb|x\d", "[^a-z]x|qq",
        "(?:" + cyr[:31] + "|" + cyr[1:32] + ")", "(?:中国人|中文字|日本)", "[一-龥]x|y[一-龥]"]
texts = ["привет error мир warning ошибка", "ax éy dy ёx", "Аб ѐв Ðг Аб\U0001d510в ѐб Аг", "éb яb x٣ x5 Яx ax qq",
         "".join([cyr[(i * 7) % 32] for i in range(300)]) + cyr + " " + cyr[1:] + cyr[0],
         "".join([chr(0x4E00 + (i * 7919) % 3000) for i in range(200)]) + "中国中文日本中国人中文字日日本 中x y中 x中 yx"]
for wi in range(len(wide)):
    rx = re.compile(wide[wi])
    for ti in range(len(texts)):
        t = texts[ti]
        print("wide", wi, ti, [m.span() for m in rx.finditer(t)], rx.subn("#", t)[1],
              [m.span() for m in [rx.search(t, 3), rx.search(t, 0, len(t) - 2)] if m is not None])
