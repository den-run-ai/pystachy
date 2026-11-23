# error: slicing an object is not supported: Sequence.__getitem__ would take a slice object, which Pystachy does not have
# a view of the list that a value of object holds takes an index, not a slice
def main() -> None:
    x: object = [1, 2, 3]
    if isinstance(x, list):
        print(x[1:])


main()
