# random.sample() takes a deque, which collections.abc.Sequence registers in CPython
import random
from collections import deque
from collections.abc import MutableSequence, Sequence

d = deque([1, 2, 3, 4, 5])
print(isinstance(d, Sequence), isinstance(d, MutableSequence))
random.seed(5)
print(random.sample(d, 3), random.sample([1, 2, 3, 4, 5], 2))
