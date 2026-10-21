# Lines of 0 to 600 bytes around the 256 bytes in which the runtime gathers a line before it
# copies it, in each newline mode, read by iteration and by readline(): a "\r\n" may fall on
# either side of that boundary, and the last line has no end
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/lines.txt"
lens = [0, 1, 254, 255, 256, 257, 258, 511, 512, 513, 600]
for sep in ["\n", "\r\n", "\r"]:
    with open(p, "w", newline="") as f:
        for n in lens:
            f.write("x" * n + sep)
        f.write("tail" * 70)
    for nl in [None, "", "\n", "\r", "\r\n"]:
        got = [(len(line), line[-2:]) for line in open(p, newline=nl)]
        g = open(p, newline=nl)
        first = g.readline()
        g.close()
        print(repr(sep), repr(nl), len(got), got[-3:], len(first), repr(first[-2:]))
os.remove(p)
os.rmdir(d)
