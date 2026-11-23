# error: cannot infer what 'Stack' objects hold before an item is stored in one: name it in the base (class Stack(list[T]))
# (the comparison method's append is no such store: the reflected comparison is compiled for None
# too, so the program's comparisons hand the method the container, as before objects were passed
# as themselves, #1739, and the program is rejected as it was. Compiled with the first
# comparison's object and the second one's container, it printed list where CPython prints Stack)
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
