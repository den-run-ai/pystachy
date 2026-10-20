# Sorting, min(), max(), membership and container equality of a subclass's objects call its
# comparison methods, which take objects of the base class (the parameter type the methods of
# a hierarchy share); a base-typed list holding both classes dispatches on each object.


class Version:
    def __init__(self, major: int, minor: int) -> None:
        self.major = major
        self.minor = minor

    def key(self) -> tuple[int, int, int]:
        return (self.major, self.minor, 0)

    def __eq__(self, other: "Version") -> bool:
        return self.key() == other.key()

    def __lt__(self, other: "Version") -> bool:
        print("lt", self, other)
        return self.key() < other.key()

    def __repr__(self) -> str:
        return "%d.%d" % (self.major, self.minor)


class Patched(Version):
    def __init__(self, major: int, minor: int, patch: int) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch

    def key(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __lt__(self, other: "Version") -> bool:
        return self.key() < other.key()

    def __repr__(self) -> str:
        return "%d.%d.%d" % (self.major, self.minor, self.patch)


ps = [Patched(1, 2, 3), Patched(1, 0, 9), Patched(1, 2, 0)]
print(sorted(ps), min(ps), max(ps), Patched(1, 0, 9) in ps, ps.count(Patched(1, 2, 0)))
print([Patched(1, 2, 3)] == [Patched(1, 2, 3)], (Patched(0, 1, 2), 1) < (Patched(0, 1, 3), 0))
mixed: list[Version] = [Version(2, 0), Patched(1, 9, 9), Version(1, 9)]
print(sorted(mixed), max(mixed), Version(1, 9) in mixed)
