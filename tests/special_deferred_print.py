# An imported class whose __eq__ Pystachy cannot compile (its parameter is annotated object):
# printing its objects, also inside a list, a tuple and a dict, uses only __repr__, so it is no
# error; nor is comparing the objects of a class without __eq__, which is identity.
from scope import sigs

t = sigs.Tagged(1)
print(t, [t], (t, 2), {"k": t})
n = sigs.Node(1)
print([n] == [n], [n] == [sigs.Node(1)], n in [n])
