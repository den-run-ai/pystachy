# A loop over dir(x) where x's classes have fields: dir() lists a field __init__ may leave
# unassigned where it is set as the loop starts (assigning it in the body changes no list made
# already); the loop's copies for each exact class read x as that class
class Case:
    def __init__(self, label: str) -> None:
        self.label = label
        self.runs = 0

    def test_base(self) -> None:
        self.runs += 1
        print(self.label, "base")


class Math(Case):
    def __init__(self, label: str, flag: bool) -> None:
        super().__init__(label)
        if flag:
            self.extra = 5

    def test_add(self) -> None:
        print(self.label, "add", 1 + 1)

    def check_extra(self) -> None:
        print("extra?")


def run(c: Case) -> None:
    for name in dir(c):
        if name.startswith("test_"):
            getattr(c, name)()
        elif not name.startswith("_"):
            print(" attr", name, hasattr(c, name))
            if name == "label" and isinstance(c, Math):
                c.extra = 9


run(Case("c"))
run(Math("m", True))
run(Math("n", False))


class Opt:
    def __init__(self, f: bool) -> None:
        self.x = 1
        if f:
            self.y = 2


a = Opt(True)
for n in dir(a):
    if not n.startswith("_"):
        print(n, getattr(a, n))
b = Opt(False)
for n in sorted(dir(b)):
    if not n.startswith("_"):
        print(n, getattr(b, n), hasattr(b, "y"))
        b.y = 3
print(dir(b)[-2:])
