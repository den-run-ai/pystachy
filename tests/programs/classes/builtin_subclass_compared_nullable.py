class Stack(list[int]):
    pass


seen = []


class Probe:
    def __eq__(self, other):
        seen.append(other)
        return len(list(other)) == 1


class Named:
    def __eq__(self, other):
        return isinstance(other, Stack)


def main() -> None:
    s = Stack()
    s.append(1)
    print(Probe() == s, s == Probe())
    print(Named() == s, s == Named())
    print(type(seen[0]).__name__, type(seen[1]).__name__)
    print(seen)
    absent: Stack = None
    try:
        print(absent == Probe())
    except TypeError as e:
        print(str(e))


main()
