import re

m = re.match(r"\d+", "42 apples")
if m:
    s: str = m.group()
    print(int(s) + 1)
