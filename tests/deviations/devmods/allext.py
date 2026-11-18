# __all__ bound at the top level and extended in an if statement's branch
# (tests/deviations/star_all_extended.py)
import sys

a = 3
b = 4
__all__ = ["a"]
if len(sys.argv) > 0:
    __all__ += ["b"]
