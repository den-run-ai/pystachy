# An imported module's __name__ == "__main__" test is false, also inside and/or
# (tests/fold_idioms.py).
import sys

v = 1
if __name__ == "__main__" and len(sys.argv) > 1:
    import loader.never
