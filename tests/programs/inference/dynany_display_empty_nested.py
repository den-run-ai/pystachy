# pystachy: dynamic-any
# An item of a display that holds an empty display, which an item before it types (the value []
# after the value [1], or after list([1]) or a comprehension, whose dry run gives a list), takes
# part in deciding whether the display's items have one type, as an item that holds none does:
# these items differ in their last value, so the display holds Any values (#782). Only an empty
# display that nothing in its item types, ([], 3) or [list(), []], takes its type from the items
# before it (dynany_display_empty.py).
x = [({"a": [1], "b": []}, 1), ({"a": [2], "b": []}, "x")]
print(x, x[1][0]["b"])
z = [{"n": [[1], []], "v": 1}, {"n": [[2], []], "v": "w"}]
print(z, len(z[1]["n"][1]))
c = [({"n": [list([1]), []]}, 1), ({"n": [list([2]), []]}, "x")]
print(c)
g = [({"n": [[i for i in range(2)], []]}, 1), ({"n": [[3], []]}, "x")]
print(g)
e = [[[1]], [list(), []]]
f = [[{"a": 1}], [dict(), {}]]
print(e, f)
