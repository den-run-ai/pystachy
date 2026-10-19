# A search for alternatives that each begin with literals or classes steps a bit-parallel filter
# of their first n items (n the least count of them, as many as 62 bits hold for all) through the
# subject, and enters the matcher only where an alternative's leading items all match. Alternatives
# of different lengths, more of them than fit, classes with members from U+0080 (a non-ASCII
# character's bits are computed as it comes), overlapping candidates, matches that end the subject,
# bounds and every operation, over subjects read in place and decoded ones.
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
