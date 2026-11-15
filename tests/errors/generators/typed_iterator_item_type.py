# error: expected int, got str
from adapter import int_iterator

print(list(int_iterator(["wrong item type"])))
