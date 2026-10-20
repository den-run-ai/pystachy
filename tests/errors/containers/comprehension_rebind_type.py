# error: comprehension_rebind_type.py:5: error: comprehension variable 'b' is list[int] in an earlier for clause and int in a later one, and a clause between them can read either (not supported)
# The last clause binds the comprehension's one b: on the second item of `for y in b`, the
# condition reads that int (CPython raises TypeError: object of type 'int' has no len()), so b
# cannot keep one type
print([y for b in [[1, 2]] for y in b if len(b) > 1 for b in [3]])
