"""Text processing: word stats, sorting, slicing, unicode, formatting."""
import sys
from collections import Counter, defaultdict, deque, OrderedDict

TEXT = """The quick brown fox jumps over the lazy dog. Der schnelle braune Fuchs springt über den faulen Hund!
Ça va très bien, merci — et vous? 日本語のテキストも含まれています。 Ελληνικά, кириллица, עברית.
Numbers: 3.14, 42, 1e10, -7; tabs\tand  double  spaces. E-mail: someone@example.com; URL: https://example.org/a?b=c#d
"""


def words(text: str) -> list[str]:
    out: list[str] = []
    cur = ""
    for ch in text:
        if ch.isalnum() or ch == "'":
            cur += ch
        elif cur:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def main() -> None:
    ws = words(TEXT)
    print(len(ws), ws[:8], ws[-5:])
    lower = [w.lower() for w in ws]
    c = Counter(lower)
    print(c.most_common(5))
    print(sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:8])
    by_len: defaultdict[int, list[str]] = defaultdict(list)
    for w in ws:
        by_len[len(w)].append(w)
    for k in sorted(by_len):
        print(k, sorted(set(by_len[k]))[:6])
    lines = TEXT.splitlines()
    print([len(line) for line in lines], [len(line.encode("utf-8")) for line in lines])
    for line in lines:
        print(repr(line[:12]), repr(line[-12:]), repr(line[5:40:7]), repr(line[::-1][:10]), line.count("e"), line.find("über"), line.rfind(" "), line.upper()[:20], line.title()[:20], line.swapcase()[:20])
    print(TEXT.split()[:6], TEXT.split(" ", 3)[:4], TEXT.rsplit(None, 2)[-2:], TEXT.partition("—")[1], len(TEXT.rpartition(".")[0]))
    print("|".join(w.center(9, "*") for w in ws[:5]), "|".join(w.ljust(7, ".") for w in ws[5:9]), "|".join(w.rjust(7) for w in ws[9:12]))
    print([w for w in ws if w.isdigit()], [w for w in ws if w.isalpha() and not w.isascii()][:6], [w for w in ws if w.istitle()][:6], [w for w in ws if w.isupper()], [w.zfill(6) for w in ws if w[0].isdigit()][:5])
    print("über".encode("utf-8"), "日本".encode("utf-8").hex(), "über".encode("latin-1"), "naïve café".encode("ascii", "replace"), "naïve".encode("ascii", "ignore"), "x€y".encode("ascii", "backslashreplace"), "aé".encode("ascii", "xmlcharrefreplace"))
    print(b"\xc3\xbcber".decode("utf-8"), b"\xff\xfeab".decode("utf-8", "replace"), b"\xff\xfeab".decode("utf-8", "ignore"), b"\xfcber".decode("latin-1"), b"caf\xc3".decode("utf-8", "backslashreplace"), repr(b"ab\xed\xa0\x80".decode("utf-8", "surrogateescape")))
    try:
        print(b"\xffabc".decode("utf-8"))
    except UnicodeDecodeError as e:
        print("UDE", e)
    try:
        print("日本".encode("ascii"))
    except UnicodeEncodeError as e:
        print("UEE", e)
    dq: deque[str] = deque(maxlen=4)
    for w in ws[:10]:
        dq.append(w)
        if len(w) > 4:
            dq.appendleft(w.upper())
    print(list(dq), dq[0], dq[-1], len(dq))
    dq.rotate(1)
    print(list(dq))
    od: OrderedDict[str, int] = OrderedDict()
    for i, w in enumerate(lower[:12]):
        od[w] = i
        if i % 4 == 3:
            od.move_to_end(lower[i - 3])
    print(list(od.items()))
    print(od.popitem(last=False), od.popitem())
    print("%-10s|%5d|%8.3f|%r" % ("left", 42, 3.14159, "q'uote"), "{:>10}|{:^10}|{:<10}|".format("r", "c", "l"), "{0}-{1}-{0}".format("a", "b"), "{a}{b!r}".format(a=1, b="x"))
    print(repr("tab\there\nnew\\line 'q' \"dq\" \x00\x7f\x80\xa0\xad ﻿\U0001f600 é"), ascii("é\U0001f600\n"), str(b"by'tes\"\n\x00\xff"))
    print("a,b,,c,".split(","), "a,b,,c,".split(",", 2), "  a  b  ".split(), "".split(), "".split(","), "abc".split("abc"), "aXbXc".rsplit("X", 1), "a\nb\r\nc\rd\n".splitlines(), "a\nb\r\nc\rd\n".splitlines(True), "a\x0bb\x0cc\x1cd\x85e f".splitlines())
    print("abc".replace("", "-"), "abc".replace("", "-", 2), "aaa".replace("a", "b", 2), "aaa".replace("aa", "b"), "abc".replace("x", "y") is "abc" or True, "".replace("", "x"), "ab".replace("b", ""), "aXbXc".replace("X", "YY", -1))
    print("hello world".find("o", 5), "hello".find("l", -2), "hello".find("", 5), "hello".find("", 6), "hello".rfind(""), "hello".index("ll"), "hello".count(""), "hello".count("l", 3), "aaaa".count("aa"), "hello".startswith(("he", "x")), "hello".endswith("lo", 0, 4), "hello".startswith("", 5), "hello".startswith("", 6))
    print("  x  ".strip(), "xxhixx".strip("x"), "abcba".strip("ab"), "  x ".lstrip(), " x  ".rstrip(), "\t\n x  ".strip() == "x", "abc".removeprefix("ab"), "abc".removesuffix("bc"), "abc".removeprefix("x"), "a-b_c d".expandtabs(), "a\tbc\tdef\tg".expandtabs(4), "\t".expandtabs(0))
    print("ß".upper(), "İ".lower() == "i̇", "ǆ".title(), "ﬁ".upper(), "Σ".lower(), "ΌΣΟΣ".lower(), "straße".casefold(), "ǅ".swapcase(), "ß".capitalize(), "ŉ".upper(), "éa".capitalize(), "o'neil mc-donald".title(), "x1y2".title(), "ab cd".capitalize())


main()
