# error: expected str, got int
from lookup import TypedLookup, dict_lookup

values: TypedLookup[int, str] = dict_lookup({0: 1})
print(values[0])
