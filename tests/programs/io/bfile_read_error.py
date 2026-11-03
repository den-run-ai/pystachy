# A read error of a binary file raises CPython's OSError, at the read, rather than ending the bytes as
# the end of the file would: reading address 0 of /proc/self/mem fails with EIO (Linux), in each
# class's read(), readline(), readlines(), readall() and iteration. The file then closes without error
def show(what: str, b: bytes) -> None:
    print(what, b)


for buffering in (-1, 0):
    print("buffering", buffering)
    if buffering == 0:
        f = open("/proc/self/mem", "rb", buffering=0)
    else:
        f = open("/proc/self/mem", "rb")
    try:
        show("read(1)", f.read(1))
    except OSError as e:
        print("read(1)", type(e).__name__, e)
    try:
        show("read()", f.read())
    except OSError as e:
        print("read()", type(e).__name__, e)
    try:
        show("readline()", f.readline())
    except OSError as e:
        print("readline()", type(e).__name__, e)
    try:
        print("readlines()", f.readlines())
    except OSError as e:
        print("readlines()", type(e).__name__, e)
    try:
        for line in f:
            show("line", line)
    except OSError as e:
        print("iteration", type(e).__name__, e)
    f.close()
    print("closed", f.closed)
f = open("/proc/self/mem", "rb", buffering=0)
try:
    show("readall()", f.readall())
except OSError as e:
    print("readall()", type(e).__name__, e)
f.close()
