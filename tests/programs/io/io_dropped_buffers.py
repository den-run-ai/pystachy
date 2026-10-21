# A file dropped without close() is closed when a collection finds it unreachable, where CPython
# closes it at once. A writable file's buffers count as the collector's memory, so files dropped
# with 48 MiB of buffers run collections, which close the files dropped by then and write out
# their text (#100); a command run by os.system sees it. The file still held has its text pending.
import os
import tempfile

d = tempfile.mkdtemp()
for i in range(48):
    f = open(d + "/" + str(i), "w", buffering=1 << 20)
    f.write(str(i) + "\n")
print(os.system("test -s " + d + "/0") == 0)
print(os.system("test -s " + d + "/47") == 0)
f.close()
print(os.system("test -s " + d + "/47") == 0)
for i in range(48):
    os.remove(d + "/" + str(i))
os.rmdir(d)
