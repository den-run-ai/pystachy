# error: split_method_index.py:4: error: 'fn[d:split:str]' object is not subscriptable
# a str's split method itself, not called, cannot be indexed (CPython's TypeError), even with [0],
# which a call's first part takes (Gen.index)
print("abc".split[0])
