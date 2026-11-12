# error: expected tuple[int], got tuple[str,str]
# Tuples of other lengths whose items have no one type do not join: a runtime-length tuple
# holds items of one type, which int and str are not
import sys

flag = len(sys.argv) > 5
mixed = (1,) if flag else ("a", "b")
print(mixed)
