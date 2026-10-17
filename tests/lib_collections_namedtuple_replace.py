# Replacements of a collections.namedtuple field choose their own specialization. The previous
# field type supplies a hint for empty lists and dicts, without constraining nonempty displays.
from collections import namedtuple

Pair = namedtuple("Pair", "left right")
p = Pair([1], {"x": 2})
print(p._replace(left=[True], right={3: 4.5}))
print(p._replace(left=[1.5], right={"y": "new"}))
print(p._replace(left=[], right={}))
print(Pair([[1]], [{"x": 2}])._replace(left=[[True]], right=[{"y": 3.5}]))
print(Pair([1.5], {"x": 2.5})._replace(left=[3], right={"y": 4}))
print(Pair([1], (1,))._replace(left=["x"], right=(True,)))
print(p)
