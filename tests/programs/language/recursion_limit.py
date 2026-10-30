# sys.setrecursionlimit() rejects a nonpositive limit before storing it.
import sys

sys.setrecursionlimit(5000)
print("set")
sys.setrecursionlimit(0)
