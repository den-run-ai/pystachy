# __getattr__ (#1536) through getattr() and hasattr(), with a literal name and with a name only
# the run time knows: the ordinary lookup first, then the method, whose AttributeError gives
# getattr()'s default or hasattr()'s False; any other exception goes on.
import sys


class Store:
    kind = "store"

    def __init__(self, full: bool) -> None:
        self.data = {"port": 80, "depth": 3}
        self.asked: list[str] = []
        if full:
            self.extra = 11

    def __getattr__(self, name: str) -> int:
        self.asked.append(name)
        if name == "boom":
            raise KeyError("boom")
        if name not in self.data:
            raise AttributeError(f"no {name}")
        return self.data[name]

    @property
    def ready(self) -> int:
        if len(self.asked) > 100:
            return 1
        raise AttributeError("not ready")

    def size(self) -> int:
        return len(self.data)


s = Store(False)
t = Store(True)
print(getattr(s, "port"), getattr(s, "port", -1), getattr(s, "nope", -1))
print(getattr(s, "extra", -5), getattr(t, "extra", -5), getattr(s, "ready", -7))
print(getattr(s, "kind"), getattr(s, "kind", "?"), getattr(s, "size")(), getattr(s, "nope", None))
print(hasattr(s, "port"), hasattr(s, "nope"), hasattr(s, "extra"), hasattr(t, "extra"))
print(hasattr(s, "ready"), hasattr(s, "kind"), hasattr(s, "size"), hasattr(s, "data"))
print(s.asked)
try:
    print(getattr(s, "nope"))
except AttributeError as e:
    print("AttributeError:", e)
try:
    print(getattr(s, "boom", 0))
except KeyError as e:
    print("KeyError:", e)
try:
    print(hasattr(s, "boom"))
except KeyError as e:
    print("KeyError:", e)
if hasattr(s, "port") and not hasattr(s, "nope"):
    print("port, and no nope")
s.data["extra"] = 99
print(s.extra, getattr(s, "extra", -5), hasattr(s, "extra"))
s.data["ready"] = 55
print(s.ready, getattr(s, "ready", -7), hasattr(s, "ready"))
for key in ("port", "depth", "zzz"):
    print(key, getattr(s, key, None), hasattr(s, key))

# names only the run time knows (the command line's and these)
names = sys.argv[1:] + ["port", "depth", "nope", "kind", "extra", "ready", "asked", "data", "boom"]
u = Store(False)
w = Store(True)
for n in names + ["size", "__class__", "__getattr__"]:
    try:
        print(n, hasattr(u, n), hasattr(w, n))
    except KeyError as e:
        print(n, "KeyError:", e)
print(u.asked, w.asked)
for n in names:
    try:
        print(n, getattr(u, n, "dflt"), getattr(w, n, None))
    except KeyError as e:
        print(n, "KeyError:", e)
    try:
        print(n, getattr(u, n))
        print(f"{n}={getattr(w, n)!r}", str(getattr(w, n)) + "!")
    except AttributeError as e:
        print(n, "AttributeError:", e)
    except KeyError as e:
        print(n, "KeyError:", e)
print(u.asked)
print(w.asked)


class Init:
    def __init__(self, a: bool) -> None:
        if hasattr(self, "early"):
            print("has early", self.early)
        if a:
            self.early = 5
        print(hasattr(self, "early"), hasattr(self, "late"))

    def __getattr__(self, name: str) -> int:
        if name == "late":
            raise AttributeError(name)
        return 3


print(Init(True).early, Init(False).early)
