from mods.constructor_hierarchy_recursive import Chain, Leaf


value = Leaf([1, 2])
value.next = Chain((3, 4))
print(value.score(), value.next.score(), isinstance(value, Chain))
value.next = value
print(value.next is value)
