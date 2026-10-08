# raise KeyboardInterrupt ends the program as CPython does: stdout is flushed and the open
# files closed, then the program is killed by SIGINT (status 130 in the shell)
import os
import tempfile

d = tempfile.mkdtemp()
f = open(d + "/k.txt", "w")
f.write("written at exit")
print(repr(open(d + "/k.txt").read()))
os.remove(d + "/k.txt")
os.rmdir(d)
print("pending output")
raise KeyboardInterrupt("stop")
