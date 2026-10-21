# A file's fileno(), and the standard streams', give select.select() real descriptors
# (stdin is /dev/null here, as tests/record.sh and tests/run.sh give it: readable at EOF)
import os
import select
import sys
import tempfile

print(sys.stdin.fileno(), sys.stdout.fileno(), sys.stderr.fileno())
print(select.select([sys.stdin.fileno()], [], [], 0))
folder = tempfile.mkdtemp()
path = os.path.join(folder, "data.txt")
w = open(path, "w")
wfd = w.fileno()
print(wfd > 2, w.fileno() == wfd)
w.write("ready\n")
w.flush()
r = open(path)
rfd = r.fileno()
print(rfd > 2, rfd != wfd)
# regular files are always ready to read and write; each list keeps its order
print(select.select([rfd, wfd], [wfd, rfd], [rfd], 0) == ([rfd, wfd], [wfd, rfd], []))
print(r.read(), end="")
r.close()
w.close()
for f in [r, w]:
    try:
        f.fileno()
    except ValueError as e:
        print("ValueError", e)
os.remove(path)
os.rmdir(folder)
