# A bool looks up the int key it equals, and a key the dict lacks raises CPython's KeyError,
# which names the bool as it is: KeyError: False, not KeyError: 0
import sys

d: dict[int, str] = {1: "one"}
if True in d:
    print(d[True])
b = len(sys.argv) > 1  # (True: the tests run with two arguments)
print(d[b], d.get(not b, "-"), (not b) in d, d.pop(not b, "-"))
print(d[False])
