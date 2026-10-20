# error: cannot infer the type of an empty dict
# A mapping's == takes any operand, which gives an empty display no type: not d, or len(d) == 0
from collections import defaultdict

d: defaultdict[str, int] = defaultdict(int)
print(d == {})
