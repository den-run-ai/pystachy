# pystachy: dynamic-any
# An item of a display that holds an empty display, which an item before it types (the value []
# after the value [1]), takes part in deciding whether the display's items have one type, as an
# item that holds none does: these items differ in their last value, so the display holds Any
# values (#782). Only an empty display that nothing in its item types, ([], 3), takes its type from
# the items before it (dynany_display_empty.py).
x = [({"a": [1], "b": []}, 1), ({"a": [2], "b": []}, "x")]
print(x, x[1][0]["b"])
z = [{"n": [[1], []], "v": 1}, {"n": [[2], []], "v": "w"}]
print(z, len(z[1]["n"][1]))
