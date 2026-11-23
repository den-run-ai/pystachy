# isinstance() with a template hierarchy's classes, both ways: an object of a subclass is one
# of the class template, and a value of the template's specialization tells its subclasses'
# objects from its own (#962).
class Node:
    def __init__(self, label, weight=1):
        self.label = label
        self.weight = weight


class Leaf(Node):
    pass


class Branch(Node):
    def __init__(self, label: str) -> None:
        super().__init__(label, 0)
        self.kids = 2


class Deep(Leaf):
    pass


items = [Node("n"), Leaf("l"), Branch("b"), Deep("d")]
for x in items:
    print(x.label, isinstance(x, Node), isinstance(x, Leaf), isinstance(x, Branch), isinstance(x, Deep), isinstance(x, (Leaf, Branch)))
leaf = Leaf("only")
print(isinstance(leaf, Node), isinstance(leaf, Leaf), isinstance(leaf, Branch), isinstance(leaf, Deep))
branch = Branch("b2")
print(isinstance(branch, Node), isinstance(branch, Leaf), isinstance(branch, Branch))
deep = Deep("d2")
print(isinstance(deep, Node), isinstance(deep, Leaf), isinstance(deep, Branch), isinstance(deep, Deep))
print(type(leaf).__name__, type(branch).__name__, type(items[3]).__name__, type(items[0]).__name__)
