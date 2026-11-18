# __getattr__ (#1536) where ordinary lookup fails for a name the class has: a field that __init__
# leaves unassigned on some path, or that the class body only annotates, reaches the method until
# it is assigned, and so does a property whose getter raises AttributeError. Any other exception,
# of the getter or of the method, goes on.
class Config:
    level: int
    kind = "cfg"

    def __init__(self, full: bool) -> None:
        self.log: list[str] = []
        if full:
            self.depth = 3
        self.name = "c"

    def __getattr__(self, name: str) -> int:
        self.log.append(name)
        if name == "boom":
            raise ValueError("boom asked")
        if name.startswith("_"):
            raise AttributeError(f"private {name}")
        return len(name)

    @property
    def area(self) -> int:
        if self.name == "c":
            raise AttributeError("area is not ready")
        return 12

    @property
    def size(self) -> int:
        return 5

    @property
    def broken(self) -> int:
        raise KeyError("broken")

    def fill(self) -> None:
        self.level = 9
        self.depth = 40

    def deep(self) -> int:
        return self.depth + self.level


a = Config(False)
b = Config(True)
print(a.depth, b.depth, a.log, b.log)
print(a.level, a.deep(), a.log)
a.fill()
print(a.level, a.depth, a.deep(), a.log)
print(a.name, a.kind, a.size, a.log)
print(a.area, a.area + 1, a.log)
a.name = "d"
print(a.area, a.log)
try:
    print(a.boom)
except ValueError as e:
    print("ValueError:", e)
try:
    print(a._hidden)
except AttributeError as e:
    print("AttributeError:", e)
try:
    print(a.broken)
except KeyError as e:
    print("KeyError:", e)
print(a.log)
b.depth += 1
print(b.depth, b.log)
c = Config(False)
c.depth += 1
c.level *= 2
print(c.depth, c.level, c.log)


class Lazy:
    def __init__(self) -> None:
        self.loads = 0
        self.ready = False

    def __getattr__(self, name: str) -> list[int]:
        if name != "rows":
            raise AttributeError(name)
        self.loads += 1
        return [1, 2, 3]

    @property
    def rows(self) -> list[int]:
        if not self.ready:
            raise AttributeError("rows are not loaded")
        return [9]


z = Lazy()
print(z.rows, z.rows, z.loads)
z.ready = True
print(z.rows, z.loads)


class Rec:
    def __init__(self, full: bool) -> None:
        if full:
            self.depth = 1

    def __getattr__(self, name: str) -> int:
        return self.depth + 1


print(Rec(True).depth, Rec(True).other)
