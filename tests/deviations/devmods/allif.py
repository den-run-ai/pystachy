# __all__ bound in an if statement's branch (tests/deviations/star_all_if.py)
import sys

a = 5
b = 6
if sys.argv[0] != "never":
    __all__ = ["a"]
