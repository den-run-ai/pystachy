# A comparison method that stores its operand, an object of a class deriving from list, in a list
# of the module that a plain list is stored in afterwards. With the object passed as itself the
# list would hold objects of the class and the later store would not compile, so the program is
# compiled with the container, as it was before objects were passed as themselves (#1739): its
# comparisons hand over such objects all or none
class Stack(list[int]):
    pass


seen = []


class Probe:
    def __eq__(self, other):
        seen.append(other)
        return True


def main() -> None:
    s = Stack()
    print(Probe() == s)
    seen.append([7])
    print(seen)


main()
