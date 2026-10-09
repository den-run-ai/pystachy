import sys

if len(sys.argv) > 5:
    util = "own"
from . import util

print(util)
