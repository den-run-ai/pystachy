# error: integer literal does not fit in 64 bits
# (a version test with a literal past 64 bits is left to run time, where such a literal is the
# error it is everywhere)
import sys

if sys.version_info < (3, 99999999999999999999):
    print("yes")
