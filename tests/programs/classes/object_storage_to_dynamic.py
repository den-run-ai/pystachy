# a module that does not opt in to dynamic Any reads and stores the values of object of a module
# that does, one of them made of an Any value there: it prints, compares and narrows them, and
# gives that module's object parameters and storage its own values
import dynstore


class Tag:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"Tag({self.n})"


def main() -> None:
    print(dynstore.get(0), dynstore.get(1), dynstore.STORE)
    dynstore.add(2.5)
    dynstore.add(None)
    dynstore.add(Tag(4))
    print(dynstore.STORE, len(dynstore.STORE))
    h = dynstore.held()
    print(h, h == 3, h is None, type(h).__name__)
    if isinstance(h, int):
        print(h + 1)
    print([dynstore.describe(v) for v in dynstore.STORE])
    print(dynstore.describe(dynstore.held()), dynstore.describe("b"))
    last = dynstore.STORE[-1]
    print(last, isinstance(last, Tag))
    if isinstance(last, Tag):
        print(last.n * 2)


main()
