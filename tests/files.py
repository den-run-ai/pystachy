# Text files as CPython's open() makes them: keyword arguments, modes, newline translation,
# "+" modes switching between reading and writing, closing, temporaries closed right away,
# file fields, print(file=...), and the standard streams as file values.
import os
import sys
import tempfile

d = tempfile.mkdtemp()
p = d + "/out.txt"
f = open(p, "w")
f.write("old\n")
f.close()
g = open(p, mode="w")
g.write("new\n")
g.close()
print(open(p).read(), end="")
h = open(file=d + "/nl.txt", mode="w", newline="\r\n")
h.write("a\nb\n")
h.close()
print(repr(open(d + "/nl.txt", newline="").read()))
open(p, "w").write("hello\n")
print(repr(open(p).read()))
total = 0
for i in range(3000):
    total += len(open(p).read())
for i in range(3000):
    k = open(p)
    total += len(k.readline())
print(total)
t = d + "/t.txt"
w = open(t, "w")
w.write("one\r\ntwo\rthree\nfour")
w.close()
r = open(t)
print(repr(r.readline()), repr(r.read()))
r.close()
for nl in ["", "\n", "\r", "\r\n"]:
    print(repr(nl), [line for line in open(t, newline=nl)], open(t, newline=nl).readlines())
print([line for line in open(t)], list(open(t)), sorted(open(t)))
for i, line in enumerate(open(t)):
    print(i, repr(line))
q = open(t)
print(repr(q.read(2)), repr(q.read(1)), repr(q.read(4)), repr(q.read(0)), repr(q.read()), repr(q.read()))
wp = open(d + "/wp.txt", "w+")
wp.write("hello\n")
print(repr(wp.read()))
wp.close()
print(repr(open(d + "/wp.txt").read()))
rp = d + "/rp.txt"
open(rp, "w").write("0123456789\n")
r = open(rp, "r+")
r.write("AB")
print(repr(r.read()))
r.close()
r = open(rp, "r+")
print(repr(r.read(2)))
r.write("X")
r.close()
a = open(rp, "a+")
print(repr(a.read()))
a.write("Z")
a.close()
print(repr(open(rp).read()))
n = open(d + "/new.txt", "x")
n.write("created\n")
n.close()
print(open(d + "/new.txt").read(), end="")
c = open(d + "/c.txt", "w", encoding="utf-8")
c.write("x")
c.close()
c.close()
print("closed twice", c.closed, c.name == d + "/c.txt", c.mode)
wl = open(d + "/wl.txt", "w")
wl.writelines(["a\n", "b\n"])
wl.flush()
print(repr(open(d + "/wl.txt").read()))
wl.close()
pf = open(d + "/pf.txt", "w")
print("a", 1, 2.5, file=pf, sep=",")
print("b", file=pf, end="", flush=True)
pf.close()
print(repr(open(d + "/pf.txt").read()))
lat = open(d + "/lat.txt", "w")
lat.write("\xe9")
lat.close()
print(len(open(d + "/lat.txt", encoding="latin-1").read()))


class Log:
    def __init__(self, path: str) -> None:
        self.f = open(path, "w")
        self.n = 0

    def line(self, s: str) -> None:
        self.f.write(s + "\n")
        self.n += 1


lg = Log(d + "/log.txt")
lg.line("a")
lg.line("b")
lg.f.close()
print(lg.n, open(d + "/log.txt").read().split(), lg.f.closed)
print("out", flush=True)
out = sys.stdout
out.write("via a variable\n")
print("x", "y", file=out, sep="-", end="!\n")
print(sys.stdout.write("w\n"), sys.stdin.name, sys.stdout.name, sys.stderr.mode)
sys.stderr.flush()
print(None, sep=None, end=None)
for name in ["out.txt", "nl.txt", "t.txt", "wp.txt", "rp.txt", "new.txt", "c.txt", "wl.txt", "pf.txt", "lat.txt", "log.txt"]:
    os.remove(d + "/" + name)
os.rmdir(d)
print(os.path.exists(d))
