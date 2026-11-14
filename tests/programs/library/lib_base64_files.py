# base64's legacy interface: encode() and decode() of binary files, encodebytes(), decodebytes()
import base64
import binascii
import io
import os
import tempfile

raw = bytes(range(256)) * 2
src = io.BytesIO(raw)
dst = io.BytesIO()
base64.encode(src, dst)
enc = dst.getvalue()
print(enc)
back = io.BytesIO()
base64.decode(io.BytesIO(enc), back)
print(back.getvalue() == raw)
for n in [0, 1, 56, 57, 58, 114]:
    out = io.BytesIO()
    base64.encode(io.BytesIO(b"x" * n), out)
    print(n, out.getvalue(), base64.encodebytes(b"x" * n) == out.getvalue())
    print(base64.decodebytes(out.getvalue()) == b"x" * n)

print("-- files on disk")
tmp = tempfile.mkdtemp()
plain = os.path.join(tmp, "plain.bin")
coded = os.path.join(tmp, "coded.txt")
again = os.path.join(tmp, "again.bin")
with open(plain, "wb") as f:
    f.write(raw[:200])
with open(plain, "rb") as i:
    with open(coded, "wb") as o:
        base64.encode(i, o)
with open(coded, "rb") as i:
    print(i.read())
with open(coded, "rb") as i:
    with open(again, "wb") as o:
        base64.decode(i, o)
with open(again, "rb") as i:
    print(i.read() == raw[:200])
for name in [plain, coded, again]:
    os.remove(name)
os.rmdir(tmp)

print("-- decodebytes")
print(base64.decodebytes(b"aGVs\nbG8=\n"), base64.decodebytes(b""), base64.decodebytes(b"aGVs!bG8="))
try:
    print(base64.decodebytes(b"aGVsbG8"))
except binascii.Error as err:
    print("Error", err)
print(base64.MAXLINESIZE, base64.MAXBINSIZE)
