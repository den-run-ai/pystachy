import re
print(bool(re.search(b"[^0-9A-F]", b"01FF")), bool(re.search(b"[^0-9A-F]", b"01fg")))
