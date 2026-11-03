# Binary files' errors: open()'s checks in CPython's order, the messages of operations on a
# closed file and of operations a file's mode does not have, and the OS's errors
import os
import tempfile

d = tempfile.mkdtemp()
p = os.path.join(d, "e.bin")
with open(p, "wb") as f:
    f.write(b"abc\ndef\n")


def opened(what: str, mode: str) -> None:
    try:
        if mode == "tb":
            open(p, "tb")
        elif mode == "rbb":
            open(p, "rbb")
        elif mode == "rwb":
            open(p, "rwb")
        elif mode == "b":
            open(p, "b")
        elif mode == "+b":
            open(p, "+b")
        elif mode == "enc":
            open(p, "rb", encoding="utf-8")
        elif mode == "errors":
            open(p, "rb", errors="strict")
        elif mode == "newline":
            open(p, "rb", newline="")
        elif mode == "both":
            open(p, "rbz", encoding="utf-8")
        elif mode == "nul":
            open(p + "\0", "rb")
        elif mode == "missing":
            open(p + ".no", "rb")
        elif mode == "dir":
            open(d, "rb")
        elif mode == "dirw":
            open(d, "wb", 0)
        print(what, "opened")
    except (ValueError, OSError) as e:
        print(what, type(e).__name__, str(e).replace(d, "D"))


for m in ["tb", "rbb", "rwb", "b", "+b", "enc", "errors", "newline", "both", "nul", "missing", "dir", "dirw"]:
    opened(m, m)

r = open(p, "rb")
w = open(os.path.join(d, "w.bin"), "wb")
rr = open(p, "rb", buffering=0)
ww = open(os.path.join(d, "ww.bin"), "wb", buffering=0)


def attempt(label: str) -> None:
    try:
        if label == "rb.write":
            print(label, "->", r.write(b"x"))
        elif label == "rb.truncate":
            print(label, "->", r.truncate())
        elif label == "wb.read":
            print(label, "->", w.read())
        elif label == "wb.readline":
            print(label, "->", w.readline())
        elif label == "raw rb.write":
            print(label, "->", rr.write(b"x"))
        elif label == "raw wb.read":
            print(label, "->", ww.read())
        elif label == "raw rb.truncate":
            print(label, "->", rr.truncate())
        elif label == "read(-2)":
            print(label, "->", r.read(-2))
        elif label == "whence 5":
            print(label, "->", r.seek(0, 5))
        elif label == "whence -1":
            print(label, "->", r.seek(0, -1))
        elif label == "seek(-1)":
            print(label, "->", r.seek(-1))
        elif label == "raw seek(-1)":
            print(label, "->", rr.seek(-1))
        elif label == "seek(max, 1)":
            r.seek(1)
            print(label, "->", r.seek(9223372036854775807, 1))
        elif label == "raw seek(min, 1)":
            rr.seek(1)
            print(label, "->", rr.seek(-9223372036854775807 - 1, 1))
        else:
            print(label, "->", r.seek(-10, 1))
    except (ValueError, OSError) as e:
        print(label, type(e).__name__, e)


for label in ["rb.write", "rb.truncate", "wb.read", "wb.readline", "raw rb.write", "raw wb.read", "raw rb.truncate", "read(-2)",
              "whence 5", "whence -1", "seek(-1)", "raw seek(-1)", "seek(max, 1)", "raw seek(min, 1)", "seek(-10, 1)"]:
    attempt(label)


def closed_ops(f) -> None:
    f.close()
    f.close()
    print(type(f).__name__, "closed", f.closed, f.name.replace(d, "D"), f.mode, repr(f).replace(d, "D"))
    for name in ["read", "readline", "readlines", "write", "writelines", "flush", "seek", "tell", "truncate", "fileno", "isatty",
                 "readable", "writable", "seekable", "iter", "next", "enter"]:
        try:
            if name == "read":
                print(" ", name, "->", f.read())
            elif name == "readline":
                print(" ", name, "->", f.readline())
            elif name == "readlines":
                print(" ", name, "->", f.readlines())
            elif name == "write":
                print(" ", name, "->", f.write(b"x"))
            elif name == "writelines":
                f.writelines([b"x"])
            elif name == "flush":
                f.flush()
            elif name == "seek":
                print(" ", name, "->", f.seek(0))
            elif name == "tell":
                print(" ", name, "->", f.tell())
            elif name == "truncate":
                print(" ", name, "->", f.truncate(0))
            elif name == "fileno":
                print(" ", name, "->", f.fileno())
            elif name == "isatty":
                print(" ", name, "->", f.isatty())
            elif name == "readable":
                print(" ", name, "->", f.readable())
            elif name == "writable":
                print(" ", name, "->", f.writable())
            elif name == "seekable":
                print(" ", name, "->", f.seekable())
            elif name == "iter":
                iter(f)
            elif name == "next":
                print(" ", name, "->", next(f))
            else:
                with f:
                    pass
        except (ValueError, OSError) as e:
            print(" ", name, type(e).__name__, e)


closed_ops(r)
closed_ops(w)
closed_ops(rr)
closed_ops(ww)
