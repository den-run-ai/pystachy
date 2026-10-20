# int, float, str and bool fields first None: int | None and the others, typed by the
# method that sets them, which compiles where module code first reads them.
class Stats:
    def __init__(self) -> None:
        self.best = None
        self.mean = None
        self.label = None
        self.done = None

    def update(self, xs: list[int]) -> None:
        self.best = max(xs)
        self.mean = sum(xs) / len(xs)
        self.label = "n=" + str(len(xs))
        self.done = len(xs) > 2


s = Stats()
print(s.best, s.mean, s.label, s.done)
s.update([3, 1, 4, 1, 5])
print(s.best, s.mean, s.label, s.done)
if s.best is not None:
    print(s.best + 1)
s.best = None
print(s.best is None, f"{s.mean!r} {s.label!r}")
