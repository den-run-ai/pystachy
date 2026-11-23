# Two specializations of a class template in one program, each with its own subclasses'
# objects: the arguments' types pick a specialization, and each one's values dispatch over
# the classes that derive from it (#962).
class Pair:
    def __init__(self, first, second):
        self.first = first
        self.second = second

    def show(self) -> str:
        return "pair " + str(self.first) + " " + str(self.second)


class Swapped(Pair):
    def show(self) -> str:
        return "swapped " + str(self.second) + " " + str(self.first)


class Named(Pair):
    def __init__(self, name: str) -> None:
        super().__init__(name, len(name))

    def show(self) -> str:
        return "named " + self.first + "=" + str(self.second)


ints = [Pair(1, 2), Swapped(3, 4)]
strs = [Pair("a", "b"), Swapped("c", "d")]
mixed = [Pair("x", 1), Swapped("y", 2), Named("zed")]
for p in ints:
    print(p.show(), p.first + p.second)
for q in strs:
    print(q.show(), q.first + q.second)
for r in mixed:
    print(r.show(), r.first * r.second)
