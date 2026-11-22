# pystachy: dynamic-any
# an empty list or dict display stored as object in a module that opts in to dynamic Any: a list or a
# dict of Any values, as its displays of items of no one type are, which a view reads
# (object_storage_empty.py: without the opt-in, of values of object)
def main() -> None:
    x: object = []
    d: object = {}
    n: object = [None]
    print(x, d, n)
    if isinstance(x, list):
        print(len(x), bool(x), list(x), x == x)
    if isinstance(d, dict):
        print(len(d), d.get("k"), list(d.keys()), "k" in d)
    if isinstance(n, list):
        print(len(n), n[0], n.count(None))


main()
