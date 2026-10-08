# A file used in one expression is closed right after it, as CPython's finalizer closes it: a
# close that fails (writing to /dev/full) is reported, "Exception ignored in: <...>", and the
# program goes on
print(open("/dev/full", "w").write("abc"))
print("x", file=open("/dev/full", "w"), end="")
print(open("/dev/full", "a", encoding="latin-1").write("y" * 100))
for line in open("/dev/null"):
    print(line)
print("after")
