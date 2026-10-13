# os.path.getsize, getmtime and getctime: os.stat()'s st_size, and its times as CPython's floats
# (the times differ from run to run: only how they compare is printed), of files, a directory and
# /dev/null, with CPython's errors for a missing file, an empty path, a path through a file and an
# embedded NUL, caught and then uncaught.
import os
import tempfile
import time

d = tempfile.mkdtemp()
p = os.path.join(d, "f.txt")
f = open(p, "w")
f.write("hello")
f.close()
print(os.path.getsize(p), os.path.getsize(os.devnull))
m = os.path.getmtime(p)
c = os.path.getctime(p)
print(m == os.path.getmtime(p), c == os.path.getctime(p), c >= m - 1, m + 0.5 > m)
print(abs(time.time() - m) < 3600, abs(time.time() - c) < 3600)
f = open(p, "a")
f.write(", world\n")
f.close()
print(os.path.getsize(p), os.path.getmtime(p) >= m, os.path.getctime(p) >= c)
print([os.path.getmtime(x) > 0 and os.path.getctime(x) > 0 for x in [p, d, os.devnull]])
for q in ["pystachy-no-such-file", "", "a\x00b", "tests/os_path_stat.py/x"]:
    try:
        print(os.path.getsize(q))
    except OSError as e:
        print("getsize", type(e).__name__, e)
    except ValueError as e:
        print("getsize", type(e).__name__, e)
    try:
        print(os.path.getmtime(q))
    except (OSError, ValueError) as e:
        print("getmtime", type(e).__name__, e)
    try:
        print(os.path.getctime(q))
    except (OSError, ValueError) as e:
        print("getctime", type(e).__name__, e)
os.remove(p)
os.rmdir(d)
print(os.path.exists(p))
os.path.getmtime(p.replace(d, "pystachy-no-such-dir"))
