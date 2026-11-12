# error: '<' not supported between instances of 'Key' and 'Key'
# pprint sorts a dict's keys and a set's items with <, which objects of a class have only where
# the class defines __lt__(). CPython orders the others by id(), which a compiled program has not.
import pprint


class Key:
    def __init__(self, n: int) -> None:
        self.n = n


print(pprint.pformat({Key(1): "a"}))
