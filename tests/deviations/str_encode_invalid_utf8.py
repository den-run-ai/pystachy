# Strict and replacing encodes of a str that holds bytes beginning no character, which a text
# file reads unchecked where CPython raises UnicodeDecodeError (docs/language/compatibility.md):
# each such byte is one character, as len() and ord() count it, also the first byte of an overlong
# sequence or of one past U+10FFFF (#1587). ASCII encodes none of them, Latin-1 each as its byte;
# a surrogate's three bytes and a valid sequence stay one character.
import os
import tempfile

path = os.path.join(tempfile.mkdtemp(), "raw.txt")
out = open(path, "wb")
out.write(b"\xe0\x80\xaf \xf0\x80\x80\xaf \xf4\x90\x80\x80 \xe0\x9f\xbfz \xed\xa0\x80 \xc3\xa9 \xe0\xa0\x80\n")
out.close()
f = open(path)
text = f.read().rstrip("\n")
f.close()
os.remove(path)
os.rmdir(os.path.dirname(path))
for word in text.split(" "):
    print(len(word), [hex(ord(c)) for c in word], word.encode("ascii", "replace"))
    for codec in ["ascii", "latin-1"]:
        try:
            print(" ", codec, word.encode(codec))
        except UnicodeEncodeError as e:
            print(" ", codec, e)
