# isinstance(x, list) narrows a value of object to a read-only view of the list it holds, whose
# items' type is not known: len() of x is the list's (as for a dict, a tuple and a set:
# object_views.py)
def main() -> None:
    x: object = [1, 2]
    if isinstance(x, list):
        print(len(x))


main()
