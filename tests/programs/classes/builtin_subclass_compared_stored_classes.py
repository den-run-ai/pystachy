# One comparison method that stores its operand, called with objects of two classes deriving
# from list: one list of the module cannot hold objects of both classes, so the comparisons hand
# over the containers, as before objects were passed as themselves (#1739). The same with a
# variable and a field that start as None, with a dict, and with an ordering
class Stack(list[int]):
    pass


class Queue(list[int]):
    pass


class Table(dict[str, int]):
    pass


seen = []
last = None
tables = []


class Probe:
    def __init__(self) -> None:
        self.kept = None

    def __eq__(self, other):
        global last
        seen.append(other)
        last = other
        self.kept = other
        return True

    def __lt__(self, other):
        seen.append(other)
        return len(other) > 1

    def __ne__(self, other):
        tables.append(other)
        return False


def main() -> None:
    s = Stack()
    s.append(1)
    q = Queue()
    q.append(2)
    p = Probe()
    print(p == s, p == q, p < s, q > p)
    print(seen, last, p.kept)
    t = Table()
    t["a"] = 1
    print(p != t, t != p)
    tables.append({"b": 2})
    print(tables)


main()
