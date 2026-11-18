# error: tuple_index.py:10: error: indexing a tuple[list[int],C] with a variable index is not supported: reference unions cannot mix native references with container members
# A variable index gives an item of the union of the items' types, which holds an object beside
# a number or a str, but not beside a list
class C:
    pass


t = ([1], C())
i = 0
print(t[i])
