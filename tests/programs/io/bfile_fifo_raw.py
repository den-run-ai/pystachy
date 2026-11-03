# FileIO's read(n) (buffering=0) is one read of the OS: from a FIFO it returns the byte that the writer
# has sent while the writer keeps the FIFO open, as CPython's does, rather than waiting for n bytes or
# the end of the file. The writer waits for the reader's acknowledgement (another FIFO) before it
# closes; a read that waited instead would get "late" too, which the writer sends after 20 seconds
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/fifo"
a = d + "/ack"
r = os.system("mkfifo " + p + " " + a)
r = os.system("(printf x; timeout 20 sh -c 'read _ < " + a + "' || printf late) > " + p + " &")
f = open(p, "rb", buffering=0)
b = f.read(10)
print(b)
if b == b"x":
    with open(a, "w") as g:
        g.write("\n")
print(f.read(10))
print(f.read(10))
f.close()
os.remove(p)
os.remove(a)
os.rmdir(d)
