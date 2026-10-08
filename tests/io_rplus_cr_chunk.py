# A "+" file's write after reads goes where CPython's text layer stopped reading ahead: the end
# of its last 8 KiB chunk, or of the next one when that chunk ends in "\r" and newline is None
# or "" (it reads on to see whether "\n" follows)
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/cr.txt"
for nl in ["None", "", "\n", "\r\n"]:
    for text in ["a" * 8191 + "\r" + "b" * 100 + "\n" + "c" * 9000, "a" * 8191 + "\r\n" + "c" * 9000,
                 "a" * 8190 + "\n\r" + "c" * 9000, "a" * 8191 + "\r"]:
        f = open(p, "w", newline="")
        f.write(text)
        f.close()
        f = open(p, "r+") if nl == "None" else open(p, "r+", newline=nl)
        n = len(f.readline())
        f.write("XYZ")
        f.close()
        g = open(p, newline="")
        print(repr(nl), n, g.read().find("XYZ"))
        g.close()
os.remove(p)
os.rmdir(d)
