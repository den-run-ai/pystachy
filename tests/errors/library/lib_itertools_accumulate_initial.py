# error: expected int, got float (compiling itertools._accumulate_initial(
# itertools.accumulate() yields its initial and then its sums, which a generator yields as one
# type: CPython yields the int 0 and then floats, so an initial of another type than the sums is
# a compile-time error (initial=0.0 is not) (lib/compatibility.md)
from itertools import accumulate

print(list(accumulate([1.5, 2.5], initial=0)))
