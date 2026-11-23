# error: comparing values of object (in a list, tuple, in, count, index, sort, min or max) is not supported: the runtime's searches and sorts do not reach their objects' methods
# a view's items are values of object, which no sort orders: sorted() of it is rejected
def main() -> None:
    x: object = [3, 1, 2]
    if isinstance(x, list):
        print(sorted(x))


main()
