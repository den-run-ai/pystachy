import sys

if len(sys.argv) > 0:
    util = "own string"
    from . import util
print("nested_own util is", util)
for i in range(2):
    from . import other
    print("other", other.W)
