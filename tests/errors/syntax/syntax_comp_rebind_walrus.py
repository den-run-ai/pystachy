# error: syntax_comp_rebind_walrus.py:7: error: comprehension inner loop cannot rebind assignment expression target 'j'
# CPython's symbol table: a for clause after a := of the same name in one comprehension (also as
# part of a target: for (a, j) in z, for j.a in z)


def never(y: list[int], z: list[int]) -> list[int]:
    return [i for i in y if (j := i) for j in z]


print("never")
