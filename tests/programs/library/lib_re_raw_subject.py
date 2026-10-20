# Pystachy reads a file's bytes that are not UTF-8 as they are, each the code point equal to the
# byte, where CPython raises UnicodeDecodeError (a documented deviation): CPython then reads the
# file as Latin-1, which gives the same code points. lib/re matches such a str in place, as a
# bytes, as it does an ASCII one, so its bytes from 128 reach the in-place engine: every result
# must be CPython's. ascii() prints the strs, which are not UTF-8. The bytes hold no valid UTF-8
# sequence: lone continuation bytes, leads before ASCII, an overlong form and, last, a truncated one.
import os
import re
import tempfile

d = tempfile.mkdtemp()
path = d + "/raw.txt"
os.system("printf '\\351abc\\311Z\\200\\377ab\\n\\240\\205\\252\\265\\337\\340x\\303(z\\340\\200\\200agggtaaa"
          "\\351\\351tttaccct\\352x\\377\\376\\n\\342\\202' > '" + path + "'")
try:
    with open(path) as f:
        s = f.read()
except UnicodeDecodeError:
    with open(path, encoding="latin-1") as f:
        s = f.read()
os.remove(path)
os.rmdir(d)
print(len(s), ascii(s), [ord(c) for c in s[:6]], ascii(s[-3:]), ascii(s[10:14]))
patterns = [r"[\x80-\xff]+", r"(?i)\xe9", r"(?i)\xc9+", r"\w+", r"\s", r"(?i)[\xc0-\xde]", r"\xe9\xe9|tttaccct",
            r"agggtaaa|tttaccct", r"[\xe0-\xef]x|ab", r"[é-ê]x|ab", r"(?i)\xb5", r"(?i)μ", r"(?i)Μ", r"(?i)ẞ", r"(?i)\xdf",
            r"\b\w", r"(.)\1", r"(?<=\xe9)a", r"(?m)^.", r"(?m)\xff$", r"[^a-z]+", r"(?a)\w+", r"\x85|\xa0", r"(?s).\Z",
            r"\d", r"[\xc3(]+", r"\xe0\x80\x80", r"(?i)(.)\1", r"(?i)[^\xe9]+", r"\B.", r"(?i)Ÿ", r"\W+",
            r"(?a)(?i)\xe9", r"(?:\xe9\xe9|\xff\xfe)\n?", r"(?:[\xe0-\xef][\x80-\xff]|ab)", r"(?:[\x80-\xff]{2}x|ab)",
            r"(?i)(?:\xe9\xe9|tt)", r"\xe9{2}", r"[\xa0-\xff]*?\xff", r"\xe2\x82$", r"(?:\xe2\x82|x\xff)"]
for pattern in patterns:
    rx = re.compile(pattern)
    print(ascii(pattern), [m.span() for m in rx.finditer(s)], ascii(rx.findall(s)[:4]), rx.subn("-", s)[1],
          len(rx.split(s)), [m.span() for m in [rx.search(s, 3), rx.search(s, 0, len(s) - 2), rx.match(s), rx.fullmatch(s)]
                             if m is not None])
print(ascii(re.sub(r"[\x80-\xff]", lambda m: "<%d>" % ord(m.group()), s)))
print(ascii(re.sub(r"(a)(g+)", r"\2\1", s)), ascii(re.split(r"[\x80-\x9f]", s)[:5]))
