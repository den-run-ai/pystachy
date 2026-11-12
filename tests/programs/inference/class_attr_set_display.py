# Class attributes typed by set displays: one set that the class and its objects share until
# an object assigns its own (mypy's checker and stub generator keep such tables).
class Checker:
    AUGMENTED = {("builtins.list", "+"), ("builtins.set", "|")}
    IGNORED = {
        "__all__",
        "__author__",
    }
    LEVELS = {1, 2, -3}

    def partial(self, name: str, op: str) -> bool:
        return (name, op) in self.AUGMENTED

    def ignored(self, name: str) -> bool:
        return name in Checker.IGNORED


class Strict(Checker):
    EXTRA = {"__slots__"}

    def ignored(self, name: str) -> bool:
        return name in self.IGNORED or name in self.EXTRA


c = Checker()
d = Checker()
s = Strict()
print(c.partial("builtins.list", "+"), c.partial("builtins.list", "|"), c.ignored("__all__"), c.ignored("x"))
print(s.ignored("__slots__"), s.ignored("__author__"), s.partial("builtins.set", "|"), sorted(Strict.LEVELS))
c.IGNORED.add("__doc__")
Checker.LEVELS.add(4)
print(sorted(d.IGNORED), sorted(Strict.IGNORED), c.IGNORED is d.IGNORED, sorted(s.LEVELS), len(Checker.AUGMENTED))
d.LEVELS = {0}
print(sorted(d.LEVELS), sorted(c.LEVELS), sorted(Checker.LEVELS))
