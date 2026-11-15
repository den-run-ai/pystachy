# error: expected TypedLookup[int, str], got TypedLookup[int, int]
from lookup import TypedLookup, dict_lookup

values: TypedLookup[int, str] = dict_lookup({0: 1})
print(values[0])
