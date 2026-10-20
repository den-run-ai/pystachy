# error: type_alias_eager_unbound.py:3: error: name 'Node' is not defined (CPython evaluates this type alias's value when the assignment runs)
# (a type statement's value would be evaluated lazily: see tests/programs/reflection/type_statement.py)
Nodes = list[Node]


class Node:
    pass


print("never")
