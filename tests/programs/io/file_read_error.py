# A read error of a text file raises CPython's OSError, at the read, rather than ending the text as the
# end of the file would: reading address 0 of /proc/self/mem fails with EIO (Linux), in read(n),
# read(), readline(), readlines() and iteration. The file then closes without error
f = open("/proc/self/mem")
try:
    print("read(1)", repr(f.read(1)))
except OSError as e:
    print("read(1)", type(e).__name__, e)
try:
    print("read()", repr(f.read()))
except OSError as e:
    print("read()", type(e).__name__, e)
try:
    print("readline()", repr(f.readline()))
except OSError as e:
    print("readline()", type(e).__name__, e)
try:
    print("readlines()", f.readlines())
except OSError as e:
    print("readlines()", type(e).__name__, e)
try:
    for line in f:
        print("line", repr(line))
except OSError as e:
    print("iteration", type(e).__name__, e)
f.close()
print("closed", f.closed)
