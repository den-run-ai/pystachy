# Two comparisons of one program with an object of a class deriving from list, of which only the
# first compiles with the object as itself: the reflected one is compiled for None too, which
# list() does not take. Both hand over the container then, as before objects were passed as
# themselves (#1739), and the list that the method stores its operand in holds lists
class Stack(list[int]):
    pass


seen = []


class Probe:
    def __eq__(self, other):
        seen.append(other)
        return len(list(other)) == 1


def main() -> None:
    s = Stack()
    s.append(1)
    print(Probe() == s)
    print(s == Probe())
    print(seen)


main()
