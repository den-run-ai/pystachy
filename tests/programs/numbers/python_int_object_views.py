# pystachy: python-int
# views of the containers that values of object hold, in a module that opts in to promoting ints:
# the entries of the tables of lists, a tuple and dicts of int and of str keys, all made at one
# line, each with its own locals' types (an int index, a key of its dict's own type)
def show(v: object) -> None:
    x: object = v
    if isinstance(x, dict):
        for k in x:
            print("key", k, x[k], x.get(k), k in x)
    elif isinstance(x, (list, tuple)):
        if len(x) > 0:
            print("first", x[0], "last", x[-1], x.index(x[-1]), x.count(x[0]))
        else:
            print("empty", x)
    else:
        print("other", x)


def main() -> None:
    values: list[object] = [[1, 2, 3], ["a", "b"], (1, "x", 2.5), (), {"a": 1, "b": 2}, {1: "one", 2: "two"}, 7, 2 ** 80]
    for v in values:
        show(v)


main()
