# unicodedata (lib/_pystachy_unicodedata.py, the stand-in Pystachy loads for the C module, on
# CPython's tables): the properties of characters of many scripts, numeric values,
# decompositions, the four normal forms (Hangul, canonical ordering, compatibility, blocked and
# excluded compositions), names and lookup() of names, aliases, named sequences and derived names,
# Unicode 3.2.0's database (ucd_3_2_0), and the errors with CPython's messages
import unicodedata
from unicodedata import category, lookup, name, normalize

chars = ["a", "Z", "5", "\u00bd", "\u00e9", "\u0301", "\u0627", "\u05d0", "\u0915", "\u093c", "\u0e01", "\u3042", "\uac00",
         "\ud7a3", "\u4e00", "\uf900", "\u2167", "\u2028", "\u200d", "\ufeff", "\u0f73", "\U0001f600", "\U0001d400",
         "\U00010400", "\U00017000", "\U0001b170", "\ue000", "\U000e0001", "\u0378", "\U0010ffff", "\x00", "\x7f", " ",
         "\ud800", "\u2329", "(", "\u00a0", "\uff21", "\u1100", "\u11a8"]
for ch in chars:
    print(ascii(ch), category(ch), unicodedata.bidirectional(ch), unicodedata.combining(ch), unicodedata.mirrored(ch),
          unicodedata.east_asian_width(ch), repr(unicodedata.decomposition(ch)), name(ch, "-"))
for ch in ["0", "9", "\u0663", "\u00b2", "\u2460", "\u00bd", "\u2155", "\u216b", "\u4e07", "\U00012432", "\u0f33", "x"]:
    print(ascii(ch), unicodedata.decimal(ch, None), unicodedata.digit(ch, None), unicodedata.numeric(ch, None),
          unicodedata.decimal(ch, -1) + 1, unicodedata.numeric(ch, 0.5) * 2)
samples = ["e\u0301", "\u00e9", "\u1e9b\u0323", "\ufb01", "\u2167", "\uac00", "\uac01", "\u1100\u1161\u11a8", "\u1100\u1161",
           "\u1100\u1176", "a\u0328\u0301\u0308", "a\u0308\u0328", "\u0344", "\u0958", "\u212b", "\u00c5\u0301",
           "A\u030a\u0301", "\u0f73\u0f71", "\U0001d15e", "\u3060", "\u304b\u3099", "\u30f0\u3099", "\u1e0b\u0323",
           "q\u0307\u0323", "\u0b47\u0b3e", "\u00c7\u0301", "x\u0301\u0301", "\u2fc4", "A\u0301\u0300\u0327", "",
           "\U0002f868", "\u0386", "\u1f80\u0345", "\u01c4", "\u00b5", "\u3392"]
for s in samples:
    for form in ["NFC", "NFD", "NFKC", "NFKD"]:
        t = normalize(form, s)
        print(form, ascii(s), ascii(t), unicodedata.is_normalized(form, s), unicodedata.is_normalized(form, t))
for n in ["LATIN SMALL LETTER A", "latin capital letter z", "GRINNING FACE", "HANGUL SYLLABLE GAG", "hangul syllable pwilh",
          "Hangul Syllable A", "CJK UNIFIED IDEOGRAPH-4E00", "cjk unified ideograph-2a6df", "CJK COMPATIBILITY IDEOGRAPH-F900",
          "TANGUT IDEOGRAPH-17000", "NUSHU CHARACTER-1B170", "LATIN CAPITAL LETTER GHA", "BYTE ORDER MARK", "BOM",
          "LATIN SMALL LETTER R WITH TILDE", "KEYCAP NUMBER SIGN", "TAMIL SYLLABLE KSSA"]:
    print(n, ascii(lookup(n)))
print(name("\uac00"), name("\ud7a3"), name("\u4e00"), name("\U0002b739"), name("\U0001b170"), name("\U00017000", None))
old = unicodedata.ucd_3_2_0
print(unicodedata.unidata_version, old.unidata_version)
for ch in ["a", "\u20ac", "\u0221", "\u4e00", "\U0001f600", "\u20b9", "\u0e3f", "\U0002f868", "\u00b2", "\u09f4", "\u3405",
           "\u1680", "\u2028", "\U00010400"]:
    print(ascii(ch), old.category(ch), old.bidirectional(ch), old.combining(ch), old.mirrored(ch), old.east_asian_width(ch),
          repr(old.decomposition(ch)), old.name(ch, "-"), old.decimal(ch, None), old.digit(ch, None), old.numeric(ch, None))
for s in ["\U0002f868", "\U0002f874", "\u2fc4", "e\u0301", "\U0001f600\u0301"]:
    print(ascii(old.normalize("NFD", s)), ascii(old.normalize("NFKC", s)), old.is_normalized("NFC", s))
print(ascii(old.lookup("LATIN SMALL LETTER A")), ascii(old.lookup("GRINNING FACE")), ascii(old.lookup("HANGUL SYLLABLE GA")))


def fail(k: int) -> None:
    try:
        if k == 0:
            name("\ue000")
        elif k == 1:
            unicodedata.decimal("x")
        elif k == 2:
            unicodedata.digit("x")
        elif k == 3:
            unicodedata.numeric("x")
        elif k == 4:
            lookup("NO SUCH NAME")
        elif k == 5:
            lookup("x" * 300)
        elif k == 6:
            normalize("NFX", "a")
        elif k == 7:
            category("ab")
        elif k == 8:
            name("")
        elif k == 9:
            old.lookup("BYTE ORDER MARK")
        elif k == 10:
            old.name("\U0001f600")
        elif k == 11:
            unicodedata.UCD("x")
        elif k == 12:
            lookup("HANGUL SYLLABLE GAX")
        elif k == 13:
            lookup("CJK UNIFIED IDEOGRAPH-04E00")
        elif k == 14:
            unicodedata.is_normalized("nfc", "a")
        elif k == 15:
            old.lookup("LATIN SMALL LETTER R WITH TILDE")
        elif k == 16:
            unicodedata.decomposition("\u00e9e")
        elif k == 17:
            unicodedata.combining("")
    except ValueError as e:
        print("ValueError:", e)
    except KeyError as e:
        print("KeyError:", e)
    except TypeError as e:
        print("TypeError:", e)


for k in range(18):
    fail(k)
print(normalize("NFX", ""), unicodedata.is_normalized("NFX", ""))
