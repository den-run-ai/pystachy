# error: 'object' object has no method
# crossing matrix (tools/crossing_matrix.py), column object, row template: without `isinstance()` narrowing


class T:
    def __init__(self, item):
        self.item = item

    def describe(self) -> str:
        return "T" + repr(self.item)

    def __repr__(self) -> str:
        return "T(" + repr(self.item) + ")"


def main() -> None:
    x: object = T('s')
    if isinstance(x, T):
        print(x.describe())
    else:
        print('not narrowed')


main()
