# Substring search where the needle's first byte is common, as each "<" of HTML is: after a few
# failed candidates runtime.py's search hands the rest to memmem, and count, replace and split go
# on with memmem from there. Also one-byte counts, and windows that cut the text.
import sys

k = len(sys.argv)
tags = ["<span>", "</span>", "<b>", "</b>", "<br>", "x", "yz", " ", "<td>", "</td>"]
parts = []
x = 7 * k
for i in range(4000):
    x = (x * 1103515245 + 12345) % 2147483648
    parts.append(tags[(x >> 8) % len(tags)])
t = "".join(parts)
print(len(t), t.count("<"))
for n in ["</span>", "</b>", "<", "</", "span>", "<b>x", "</span><", "<i>", "</td><td>", "y", "<br><br>"]:
    at = 0
    j = t.find(n)
    while j >= 0:
        at += j
        j = t.find(n, j + 1)
    r = t.replace(n, "#")
    print(repr(n), t.count(n), t.count(n, 7, -9), t.count(n, 1000, 1100), at, t.find(n, 100, 5000), t.rfind(n), n in t)
    print(len(r), r.count("#"), r[:40], len(t.split(n)), t.split(n, 3)[:2], t.partition(n)[0][-12:])
