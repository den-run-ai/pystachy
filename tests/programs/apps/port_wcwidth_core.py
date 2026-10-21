# wcwidth's wcwidth() and wcswidth(): the cases of its own test suite (tests/test_core.py,
# test_emojis.py, test_ambiguous.py and test_ucslevel.py of wcwidth 0.9.2, run under pytest there)
# as a program. For each phrase it prints the code points, the width of each character and the
# width of the phrase. The cases of the API the port leaves out (width(), wcstwidth(), ljust(),
# wrap(), clip(), the C extension and the legacy module) are left out too.
import wcwidth
from wcwidth import list_versions, wcswidth
from wcwidth import wcwidth as wcw


def chars(s: str) -> list[str]:
    # the characters of s: Pystachy's str holds UTF-8 bytes (len("\u00e9") == 2), CPython's
    # holds code points, one per character
    out: list[str] = []
    i = 0
    while i < len(s):
        n = 1
        if len("\u00e9") == 2:
            b = ord(s[i])
            n = 1 if b < 0xC0 else 2 if b < 0xE0 else 3 if b < 0xF0 else 4
        out.append(s[i:i + n])
        i += n
    return out


def show(name: str, phrase: str) -> None:
    cs = chars(phrase)
    print(name, " ".join(["%04X" % ord(c) for c in cs]), [wcw(c) for c in cs], wcswidth(phrase))


# test_core.py
show("empty", "")
show("basic", "hello\x00world")
show("hello_jp", "\u30b3\u30f3\u30cb\u30c1\u30cf, \u30bb\u30ab\u30a4!")
print("substr", wcswidth("\u30b3\u30f3\u30cb\u30c1\u30cf, \u30bb\u30ab\u30a4!", 7))
show("null", "abc\x00def")
print("null n=7", wcswidth("abc\x00def", 7))
show("csi", "\x1b[0m")
show("combining", "--\u05bf--")
show("cafe", "cafe\u0301")
show("enclosing", "\u0410\u0488")
show("balinese", "\u1b13\u1b28\u1b2e\u1b44")
show("adeg adeg", "\u1b44")
show("kr_jamo", "\u1100\u1161")
show("jamo filler", "\u1100\u1160")
show("devanagari", "\u0915\u094d\u0937\u093f")
show("tamil", "\u0b95\u0bcd\u0bb7\u0bcc")
show("kannada", "\u0cb0\u0ccd\u0c9d\u0cc8")
show("kannada_2", "\u0cb0\u0cbc\u0ccd\u0c9a")
show("bengali nukta mc", "\u09af\u09bc\u09c7")
show("mc", "\u09b9\u09af\u09bc\u09c7\u099b\u09c7")
show("mc", "\u0915\u09be\u0999\u09cd\u0996\u09be")
# test_virama_conjunct, test_virama_conjunct_mc_vowel, test_virama_mc_category_overlap,
# test_virama_conjunct_invisible_stacker: each phrase is 2 cells wide but the last (0)
for phrase in ["\u0999\u09cd\u0997\u09c7", "\u0915\u094d\u0924\u093f", "\u0915\u094d\u0930\u093f",
               "\u0a95\u0acd\u0a95\u0acb", "\u0938\u094d\u0924\u094d\u0930", "\u0938\u094d\u0924",
               "\u0915\u094d ", "\u09a4\u09cd\u200d\u09aa", "\u0915\u094d\u200d\u0924",
               "\u0d15\u0d4d\u0d15\u0d41\u0d02", "\u0915\u094d\u0924\u0941\u0902",
               "\u0995\u09cd\u09a4\u09bf", "\u0995\u09cd\u09a4", "\u0995\u09bf",
               "\ua9a0\ua9c0\ua9b1\ua9c0\ua9ae", "\ua9a0\ua9c0\ua9b1", "\u1b04\u1b44\u1b05",
               "\u1000\u1039\u1000", "\u1000\u1039\u1000\u1039\u1002", "\u1000\u1039\u200d\u1000",
               "\u1782\u17d2\u1782\u17c1", "\u1780\u17d2\u1780", "\U000111c0\U000111c0"]:
    show("virama", phrase)
show("zwj at end", "a\u200d")
print("n exceeds", wcswidth("hello", n=999), wcswidth("\u30b3\u30f3", n=999))
print("soft hyphen", wcw("\u00ad"))
# test_prepended_concatenation_mark_width: each is 1 cell wide
for cp in [0x0600, 0x0601, 0x0602, 0x0603, 0x0604, 0x0605, 0x06DD, 0x070F, 0x0890, 0x0891, 0x08E2,
           0x110BD, 0x110CD]:
    print("prepended %04X" % cp, wcw("%c" % cp))

# test_emojis.py
show("zwj", "\U0001f469\U0001f3fb\u200d\U0001f4bb")
show("unfinished zwj", "\U0001f469\U0001f3fb\u200d")
show("another zwj", "\u26f9\U0001f3fb\u200d\u2640\ufe0f")
show("longer zwj", ("\U0001f9d1\U0001f3fb\u200d\u2764\ufe0f\u200d\U0001f48b\u200d\U0001f9d1"
                    "\U0001f3fd") * 2)
show("ri 1", "\U0001f1fa")
show("ri 2", "\U0001f1fa\U0001f1f8")
show("ri 3", "\U0001f1fa\U0001f1f8\U0001f1e6")
show("ri 4", "\U0001f1fa\U0001f1f8\U0001f1e6\U0001f1fa")
show("zwj after non-emoji", "xx\u200d\U0001f384")
show("zwj after non-emoji", "a\u200d\U0001f600")
show("zwj after non-emoji", "\u4e16\u200d\U0001f600")
show("fitzpatrick", "\U0001f3fb")
show("fitzpatrick after emoji", "\U0001f469\U0001f3fb")
show("vs16", "\u2640\ufe0f")

# test_ambiguous.py
for c in ["\u00a1", "\u00a7", "\u00b0", "\u00b1", "\u00d7", "\u00f7", "\u2460", "\u2500", "\u25a0",
          "\u2605"]:
    print("ambiguous %04X" % ord(c), wcw(c), wcw(c, ambiguous_width=2))
print("mixed", wcswidth("\u4e2d\u00b1"), wcswidth("\u4e2d\u00b1", ambiguous_width=2))
print("wide", wcw("\u4e2d"), wcw("\u4e2d", ambiguous_width=2), wcw("\u4e2d", ambiguous_width=1))
for aw in [-1, 0, 3, 99]:
    print("clamped", aw, wcw("\u2460", ambiguous_width=aw), wcswidth("\u2460", ambiguous_width=aw))

# test_ucslevel.py
versions = list_versions()
(only,) = list_versions()
print("versions", len(versions), versions[0], versions, only)
latest = versions[-1]
for v in ["latest", "auto", "4.1.0", "9.0.0", "invalid", "999.0.0", "x.y.z", "8", "5.0.5"]:
    print("wcmatch", v, wcwidth._wcmatch_version(v) == latest)
for v in ["4.1.0", "latest", "invalid"]:
    print("unicode_version", v, wcw("A", unicode_version=v), wcswidth("hello", unicode_version=v))
print(wcwidth.__version__, wcwidth.HAS_C_EXTENSION)
