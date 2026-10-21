# The characters of a str, as unicodedata's functions take them: re.findall("(?s).", s) gives
# them (iterating a Pystachy str gives its bytes, lib/compatibility.md), here to strip the
# combining marks of a decomposed text and name them
import re
import unicodedata

for text in ["\u00e9t\u00e9 \u00c5ngstr\u00f6m", "Cr\u00e8me br\u00fbl\u00e9e", "\u1ea0\u0300\u0301 \uac00\U0001f600", "plain"]:
    nfd = unicodedata.normalize("NFD", text)
    chars = re.findall("(?s).", nfd)
    print(len(chars), "".join([c for c in chars if unicodedata.combining(c) == 0]))
    print([unicodedata.name(c) for c in chars if unicodedata.combining(c) != 0])
    print([unicodedata.category(c) for c in re.findall("(?s).", text)])
