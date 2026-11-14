# error: set_none_union_wider.py:5: error: set.union() of set[str] for a set of None is not supported: a set holds elements of one type
# (the operators make a set of both types, {None} | {"a"}; a method's result has its set's type)
n: set[None] = {None}
s: set[str] = {"a"}
print(n.union(s))
