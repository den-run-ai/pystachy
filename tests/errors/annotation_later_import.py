# error: annotation_later_import.py:3: error: name 'Bag' is not defined
# A def evaluates its annotations when it runs: an import further on binds the name too late.
def size(b: Bag) -> int:
    return b.n


from emods.special import Bag

print(size(Bag(3)))
