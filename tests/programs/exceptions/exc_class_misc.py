# Corners of exception classes: fields an __init__ may leave unassigned, class-body fields, the
# name of an except clause bound to objects of different classes, objects in containers, a
# raise through the runtime's sort, and an uncaught exception whose str() is empty.


class Base(Exception):
    def __init__(self, a: int):
        super().__init__(a)
        self.a = a
        if a > 0:
            self.pos = a

    def show(self) -> str:
        return f"a={self.a} pos={self.pos}"


class Sub(Base):
    extra: str = "x"

    def __init__(self, a: int, b: str):
        self.b = b
        super().__init__(a)


class Lazy(Base):
    note: str
    count: int = 0


class Problem(Exception):
    pass


class Key:
    def __init__(self, k: int):
        self.k = k

    def __lt__(self, other: "Key") -> bool:
        if self.k == 3 or other.k == 3:
            raise Base(-3)
        return self.k < other.k


for o in [Base(1), Base(0), Sub(2, "q"), Sub(-1, "r")]:
    try:
        print(o.show(), repr(o))
    except AttributeError as e:
        print("AttributeError:", e)
s = Sub(4, "w")
print(s.extra, s.b, s.show())
s.extra = "y"
print(s.extra, Sub(5, "z").extra)
z = Lazy(3)
try:
    print(z.note)
except AttributeError as e:
    print("AttributeError:", e)
z.note = "set"
z.count += 2
print(z.note, z.count, z.show(), repr(z))


def classify(n: int) -> str:
    r = ""
    try:
        if n == 0:
            raise Sub(1, "s")
        if n == 1:
            raise ValueError("v")
        if n == 2:
            raise Problem("p")
        raise Base(n)
    except Sub as e:
        r = "sub " + e.b
    except ValueError as e:
        r = "value " + str(e)
    except (Problem, KeyError) as e:
        r = "problem " + repr(e)
    except Base as e:
        r = f"base {e.a}"
    return r


print([classify(i) for i in range(4)])
for i in range(3):
    try:
        if i == 0:
            raise Base(0)
        if i == 1:
            raise OSError("os")
        raise Sub(7, "t")
    except Sub as e:
        print("module sub", e.b)
    except Base as e:
        print("module base", e.a)
    except OSError as e:
        print("module os", e)
try:
    print(e)
except NameError as x:
    print("NameError:", x)
keys = [Key(5), Key(1), Key(3), Key(2)]
try:
    keys.sort()
except Base as e:
    print("sort raised", e.a, len(keys), [k.k for k in keys])
by_kind: dict[str, list[Base]] = {"subs": [Sub(1, "a"), Sub(2, "b")], "bases": [Base(3)]}
print(by_kind)
pairs: list[tuple[str, Base]] = [("one", Base(1)), ("two", Sub(2, "two"))]
for name, err in pairs:
    print(name, err, err.a)
latest: Base | None = None
for i in range(3):
    try:
        raise Base(i * 10)
    except Base as e:
        latest = e
if latest is not None:
    print("latest:", repr(latest), latest.a)

def kind(e: Base | None) -> str:
    return f"{type(e).__name__} {isinstance(e, Sub)} {isinstance(e, Base)} {isinstance(e, (Lazy, Problem))} {isinstance(e, ValueError)} {isinstance(e, Exception)}"


print(kind(Base(1)), "|", kind(Sub(1, "s")), "|", kind(Lazy(2)), "|", kind(None))
for x in [ValueError("v"), KeyError("k"), OSError("o")]:
    try:
        raise x
    except Exception as e:
        print(type(e).__name__, isinstance(e, LookupError), isinstance(e, (OSError, KeyError)), isinstance(e, Base), isinstance(e, BaseException))
try:
    raise Sub(3, "three")
except Exception as e:
    print(type(e).__name__, isinstance(e, Base), isinstance(e, Sub), isinstance(e, Lazy), isinstance(e, ValueError))
raise Problem()
