# readlines(hint) stops after the total byte count exceeds hint, not when it equals it.
# The next line and logical position must agree for raw and both buffered reader classes.
import os
import tempfile


def check(f) -> None:
    print(type(f).__name__)
    for hint in [-1, 0, 1, 2, 3, 4, 6, 7]:
        f.seek(0)
        print(hint, f.readlines(hint), f.tell(), f.readline())
    f.seek(0)
    print(None, f.readlines(None), f.tell())


p = os.path.join(tempfile.mkdtemp(), "lines.bin")
with open(p, "wb") as f:
    f.write(b"a\nb\nc\n")
with open(p, "rb") as f:
    check(f)
with open(p, "r+b", buffering=2) as f:
    check(f)
with open(p, "rb", buffering=0) as f:
    check(f)
