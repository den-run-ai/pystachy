# fnmatch's range translation must compare, skip and remove whole characters, even when
# the str's indices count UTF-8 bytes. CPython supplies the translations and matching names.
import fnmatch

NAMES = ["", "a", "b", "x", "z", "é", "ê", "ë", "中", "丰", "串", "😀", "😁", "😂", "😃", "😄",
         "-", "]", "[", "!", "^", "&", "~", "|", "\\", "éx", "xé", "café.txt", "cafê.txt"]
PATTERNS = [
    "[ê-é]", "[!ê-é]", "[文-中]", "[!文-中]", "[😃-😀]", "[!😃-😀]", "[é-a]", "[!é-a]",
    "[é-cx]", "[!é-cx]", "[é-ê中-丰]", "[!é-ê中-丰]", "[ê-é中-丰]", "[é-ê丰-中]", "[ê-é丰-中]",
    "[!ê-é丰-中]", "[é-ê-文]", "[é-ê--]", "[é-ê-x]", "[é--]", "[--é]", "[!é--]",
    "[é-]", "[-é]", "[!-é]", "[]é-ê]", "[!]é-ê]", "[^é-ê]", "[é-ê&~|]", "[é-ê\\]",
    "[é-ê[]", "[é-ê", "[😀-😃é-ê]", "[😃-😀é-ê]", "[!😃-😀ê-é]", "caf[é-ê].txt",
]
for endpoints in [["a", "z"], ["é", "ê"], ["中", "丰"], ["😀", "😃"]]:
    for lo in endpoints:
        for hi in endpoints:
            PATTERNS.append("[" + lo + "-" + hi + "]")
            PATTERNS.append("[!" + lo + "-" + hi + "]")

for pat in PATTERNS:
    print(pat, fnmatch.translate(pat), fnmatch.filter(NAMES, pat))
    # Calls through the existing cached matcher must agree after the initial compilation.
    print([name for name in NAMES if fnmatch.fnmatchcase(name, pat)])
