# OSError(errno, strerror[, filename]) is "[Errno n] strerror", of the subclass the errno names.
for a in [1, 2, 13, 17, 21, 999, 11]:
    try:
        raise OSError(a, "msg")
    except FileNotFoundError as e:
        print("FNF", e, repr(e))
    except PermissionError as e:
        print("PE", e, repr(e), type(e).__name__)
    except OSError as e:
        print("OS", e, repr(e), type(e).__name__)
e = OSError(2, "No such file", "a.txt")
print(e, repr(e), isinstance(e, FileNotFoundError))
e = OSError(2, "x", None)
print(e, repr(e))
e = FileNotFoundError(13, "y")
print(type(e).__name__, e)
e = IOError("s", "t")
print(type(e).__name__, e, repr(e))
e = ImportError("x", name="m", path="p")
print(repr(e), str(e))


class I(ImportError):
    def __init__(self, m: str) -> None:
        super().__init__(m, name="modx")


i = I("cannot import")
print(str(i), repr(i))


class A(AttributeError):
    def __init__(self) -> None:
        super().__init__("msg", obj=3, name="n")


print(repr(A()))


class StoreError(OSError):
    pass


class Sub(StoreError):
    def __init__(self, path: str) -> None:
        super().__init__(2, "gone", path)
        self.path = path


e2 = StoreError(2, "no such file")
print(e2, repr(e2), type(e2).__name__)
s = Sub("x.db")
print(s, repr(s), s.path)
try:
    raise s
except FileNotFoundError:
    print("no")
except OSError as x:
    print("OSError", x)
raise OSError(21, "Is a dir", "/tmp")
