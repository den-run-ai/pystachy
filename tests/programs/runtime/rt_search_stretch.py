# Substring search that goes to memmem after a few failed candidates (a head of HTML tags), then
# finds the text sparse: memmem runs for a stretch, then runtime.py's search counts the candidates
# again. Occurrences at each place around the stretch's end; alternating dense and sparse runs;
# one-byte counts over runs of the byte, dense stretches and sparse ones.
import sys

k = len(sys.argv)
para = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor " * 13
t = "<html><head><title>x</title></head><body>" * k + ("<p>" + para + "</p>\n") * 300
print(len(t), t.count("</p>"), t.count("</p>", 50, -50), t.find("</table>"), t.find("</body>"), "</html>" in t)
r = t.replace("</p>", "</P>")
print(len(r), r.count("</P>"), len(t.split("</p>")), len(t.split("</p>", 7)), t.rfind("</p>"))
at = 0
j = t.find("</p>")
while j >= 0:
    at += j
    j = t.find("</p>", j + 4)
print(at)

# an occurrence at each place around the end of the first stretch (16 * len(n) + 256 bytes),
# alone or after another
s = 0
for n in ["</p>", "</span>", "</"]:
    d = 16 * len(n) + 256
    for head in ["<x" * 3, "<" * 40]:
        for p in range(d - 40, d + 10):
            for h in [head + "y" * p + n, head + "y" * 5 + n + "y" * p + n + "<y" * 3]:
                s += h.find(n) + 3 * h.count(n) + 5 * len(h.split(n)) + 7 * len(h.replace(n, "#"))
print(s)

# runs of dense failing candidates and sparse text, alternating
parts = []
x = 5 * k
for i in range(300):
    x = (x * 1103515245 + 12345) % 2147483648
    parts.append(["<b>", "<x", "<", "</", "<i>"][x % 5] * ((x >> 8) % 90))
    parts.append("words " * ((x >> 16) % 120))
    if x % 3 == 0:
        parts.append("</span>")
t = "".join(parts)
for n in ["</span>", "</b>", "</", "<b>x", "words </span>"]:
    print(repr(n), t.count(n), t.find(n), len(t.split(n)), len(t.replace(n, "<>")), n in t, t.count(n, 1000, 9000))

# one-byte counts: a run of the byte, a byte every 2 or 3 places, dense stretches among sparse ones
for t, c in [("a" * 1000 * k, "a"), ("abracadabra " * 500, "a"), (("x" * 50 + "ab" * 40) * 30, "a"), ("<td>x</td>" * 400, "<")]:
    print(t.count(c), t.count(c, 3, -3), t.count(c, 17, 401))
