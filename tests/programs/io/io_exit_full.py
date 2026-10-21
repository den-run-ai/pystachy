# Files still open at the end are closed then, in the order they were opened; a close that
# fails (on /dev/full) is reported as CPython's finalizer reports it and the status stays 0
import os
import tempfile

d = tempfile.mkdtemp()
a = open("/dev/full", "w")
a.write("lost")
b = open(d + "/kept.txt", "w")
b.write("kept")
c = open("/dev/full", "w", encoding="UTF8")
c.write("lost too")
print(repr(open(d + "/kept.txt").read()))
os.remove(d + "/kept.txt")
os.rmdir(d)
print("end")
