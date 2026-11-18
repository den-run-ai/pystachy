# Case methods keep a byte that begins no character and give it no case, among characters
# that they map as CPython does. A text file reads such bytes unchecked, where CPython raises
# UnicodeDecodeError (docs/language/compatibility.md#unicode).
import os
import tempfile

path = os.path.join(tempfile.mkdtemp(), "raw.txt")
out = open(path, "wb")
out.write(b"a\xffb \xc3 \xe9cole \xc3\x89cole\xe9 x\xc3\xa9\x80Y \xcf\x83\xff\xce\xa3 \xce\x91\xce\xa3\xff \xf0\x9f\x98 \xce\x91\xff\xce\xa3\n")
out.close()
f = open(path)
text = f.read().rstrip("\n")
f.close()
os.remove(path)
os.rmdir(os.path.dirname(path))
for word in text.split(" "):
    print(ascii(word), ascii(word.upper()), ascii(word.lower()), ascii(word.casefold()), ascii(word.title()),
          ascii(word.capitalize()), ascii(word.swapcase()), word.isupper(), word.islower(), word.istitle())
