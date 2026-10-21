# close() of a FIFO whose reader has gone flushes into a broken pipe: BrokenPipeError, CPython's
# OSError subclass for EPIPE, as for a write
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/fifo"
m = d + "/gone"
r = os.system("mkfifo " + p)
r = os.system("(sh -c 'exec 3<" + p + "'; : > " + m + ") &")
f = open(p, "w")
f.write("data")
while not os.path.exists(m):
    pass
os.remove(m)
os.remove(p)
os.rmdir(d)
print("closing")
f.close()
print("not reached")
