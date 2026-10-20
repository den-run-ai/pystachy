# error: dict[...] as a value is not supported (only annotations may name a type
# Fields is bound twice, so it is no type alias: the subscript is a value.
Fields = dict[str, int]
Fields = dict[str, float]
print("never")
