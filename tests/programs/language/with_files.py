# with open(...) as f: the file closes at the end of the block and when break, continue or
# return leave it.
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/w.txt"
with open(p, "w") as f:
    f.write("line 1\n")
    f.write("line 2\n")
print(f.closed, open(p).read().split("\n"))
with open(p) as f, open(d + "/copy.txt", "w") as g:
    for line in f:
        g.write(line.upper())
print(f.closed, g.closed, repr(open(d + "/copy.txt").read()))


def first(path: str) -> str:
    with open(path) as h:
        for line in h:
            return line.strip()
    return ""


print(first(p))
k: list[str] = []
for i in range(3):
    with open(d + "/n" + str(i), "w") as w:
        w.write(str(i))
        if i == 1:
            continue
        w.write("!")
for i in range(3):
    with open(d + "/n" + str(i)) as r:
        k.append(r.read())
        if i == 1:
            break
print(k, r.closed)
with open(d + "/n2", "a"):
    pass
with open(d + "/n2") as r2:
    data = r2.read()
print(data)
for nm in ["w.txt", "copy.txt", "n0", "n1", "n2"]:
    os.remove(d + "/" + nm)
os.rmdir(d)
