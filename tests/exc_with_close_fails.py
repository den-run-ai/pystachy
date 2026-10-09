# An exception leaves a with block whose file's close then fails (/dev/full has no room for
# what was written): the OSError of the close replaces the exception in flight, inside the try
# statement around, whose clauses and finally block see it, as CPython's __exit__ raises it.
def write(f_path: str, n: int) -> None:
    with open(f_path, "w") as f:
        f.write("x" * n)
        int("bad")


try:
    with open("/dev/full", "w") as f:
        f.write("x")
        int("bad")
except ValueError as e:
    print("value:", e)
except OSError as e:
    print("os:", e)
try:
    write("/dev/full", 3)
except OSError as e:
    print("os from a function:", e)
try:
    with open("/dev/full", "w") as f, open("/dev/full", "w") as g:
        f.write("f")
        g.write("g")
        raise KeyError("k")
except KeyError:
    print("key")
except OSError as e:
    print("os, both:", e)
n = 0
for i in range(3):
    try:
        with open("/dev/full", "w") as f:
            f.write("y")
            raise ValueError(i)
    except OSError:
        n += 1
    finally:
        n += 10
print(n)
try:
    with open("/dev/full", "w") as f:
        f.write("x")
        raise ValueError("inner")
finally:
    print("finally")
