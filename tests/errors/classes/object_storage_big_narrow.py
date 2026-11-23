# error: narrowing a value of object to bool | int by isinstance() is not supported where it may hold a promoting int (a module that opts in to promoting ints stored one), which bool | int holds only within 64 bits
# isinstance(x, int) in a module that does not opt in to promoting ints narrows x to a 64-bit int
# (or a bool), which cannot hold the promoting int that a module that opts in stored as object
import emods.object_big as ob


def main() -> None:
    x = ob.BIG
    if isinstance(x, int):
        print(x + 1)


main()
