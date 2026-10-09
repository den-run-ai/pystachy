# sys.setrecursionlimit() checks its argument (Pystachy's recursion is limited by the native
# stack alone, so the limit changes nothing)
import sys

sys.setrecursionlimit(5000)
print("set")
sys.setrecursionlimit(0)
