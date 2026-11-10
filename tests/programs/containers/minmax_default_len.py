# min() and max() with default= take an iterable object's items through __iter__ alone, as
# they do without it: they never ask for its __len__, which list() does as a hint, so one
# that raises or counts its calls does not run
class Bag:
    def __init__(self, held: list[int]) -> None:
        self.held = held

    def __iter__(self):
        return iter(self.held)

    def __len__(self) -> int:
        raise ValueError("no length")


class Counted:
    def __init__(self, held: list[str]) -> None:
        self.held = held
        self.asked = 0

    def __iter__(self):
        for word in self.held:
            yield word

    def __len__(self) -> int:
        self.asked += 1
        return len(self.held)


class Stepped:
    def __init__(self, stop: int) -> None:
        self.at = 0
        self.stop = stop
        self.asked = 0

    def __iter__(self) -> "Stepped":
        return self

    def __next__(self) -> int:
        if self.at >= self.stop:
            raise StopIteration
        self.at += 1
        return self.at * 7 % 5

    def __len__(self) -> int:
        self.asked += 1
        raise TypeError("unsized")


bag = Bag([3, 1])
print(max(bag, default=0), min(bag, default=0), max(Bag([]), default=-1), min(bag, key=lambda v: -v, default=None))
words = Counted(["bb", "a", "ccc"])
none = Counted([])
print(max(words, default=""), min(words, key=len, default=""), max(none, default=None), min(none, key=len, default="?"), words.asked, none.asked)
steps = Stepped(4)
done = Stepped(0)
print(max(steps, default=-1), max(steps, default=-1), min(done, default=None), steps.asked, done.asked)
try:
    print(len(bag))
except ValueError as e:
    print("ValueError", e)
