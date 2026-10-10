import sys
sys.path.insert(0, sys.argv[1])
import fu
r, names = fu.probe(lambda: fu.deep())
print("result", r)
for n in names: print(" ", n)
