# The comparison's first append types the bare base while retaining the subclass. A
# reflected call's possible None arm must not make other comparisons lose that class.
class Stack(list):
    pass


class Probe:
    def __eq__(self, other):
        other.append(5)
        print(type(other).__name__, other)
        return True


def main() -> None:
    s = Stack()
    print(Probe() == s)
    s.append(6)
    print(s, s == Probe())


main()
