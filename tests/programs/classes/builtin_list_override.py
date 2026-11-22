# list's own operations never call a subclass's methods: C(xs), +=, insert() and list.extend()
# fill the list as list does where the class defines append() or extend(), which run only where
# the program calls them, and reach list's own through super() or list.extend(self, xs).


class Logged(list[int]):
    def __init__(self, xs: list[int]) -> None:
        super().__init__(xs)
        self.log: list[str] = ["init"]

    def append(self, x: int) -> None:
        self.log.append("append " + str(x))
        super().append(x * 10)

    def extend(self, xs: list[int]) -> None:
        self.log.append("extend " + str(len(xs)))
        list.extend(self, xs)


class Bare(list[int]):
    def extend(self, xs: list[int]) -> None:
        print("never called by Bare(xs) or +=")


s = Logged([1, 2])
s.append(3)
s.extend([4, 5])
s += [6]
s.insert(0, 0)
print(s, s.log)
b = Bare([7, 8])
b += [9]
b.extend([1])
print(b, len(b))
