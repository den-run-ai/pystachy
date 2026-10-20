# error: tuple_index.py:10: error: indexing a tuple[int,C] with a variable index is not supported: reference unions cannot mix native references with scalar or container members
# A variable index gives an item of the union of the items' types, which cannot hold both an
# object and an int
class C:
    pass


t = (1, C())
i = 0
print(t[i])
