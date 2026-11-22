# error: 'Sequence[object]' object has no method 'append' (Sequence[object] is a read-only view of a list or a tuple that a value of object holds
# a view of the list that a value of object holds changes nothing: its item type is not known
def main() -> None:
    x: object = [1]
    if isinstance(x, list):
        x.append(2)
    print(x)


main()
