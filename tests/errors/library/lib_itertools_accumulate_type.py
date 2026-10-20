# error: expected int, got str (compiling itertools._accumulate(
# itertools.accumulate() yields its first item and then what the function returns, which a
# generator yields as one type (lib/compatibility.md)
from itertools import accumulate

print(list(accumulate([1, 2, 3], lambda total, x: str(total) + str(x))))
