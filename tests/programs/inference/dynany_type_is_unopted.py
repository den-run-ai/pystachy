# Deliberately no dynamic-any directive: dyntypevalues opts in and gives this module Any values.
# A module that opts in compares type() results as class values; this one compares the exact
# types of their boxes (reflection.py's refl_dyn_type_cmp, runtime.c's pys_dyn_same_type), as
# CPython does: a bool is no int, both list layouts are list, functions are one type. Typed
# operands give the type of the value they hold (dynamic.py's dyn_value_type): None's for an
# optional that is None, a union member's by its tag.
import dyntypevalues


class Local:
    pass


v = dyntypevalues.values()
for k in v:
    x = v[k]
    print(k, type(x) is int, type(x) == bool, type(x) is float, type(x) is not str, type(x) is type(None),
          type(x) is list, type(x) != dict, type(x) is tuple, type(x) is dyntypevalues.Point)
pairs = [("int", "bool"), ("ints", "mixed"), ("mixed", "ints"), ("double", "triple"), ("gen", "gen2"),
         ("listiter", "listiter2"), ("listiter", "tupleiter"), ("point", "point"), ("dict", "tuple"),
         ("none", "int"), ("double", "gen")]
for a, b in pairs:
    print(a, b, type(v[a]) is type(v[b]), type(v[a]) != type(v[b]))
local_list = [1, 2]
local_dict = {"k": 1}
local_tuple = (1, 2)
maybe: list[int] | None = None
maybe_list: list[int] | None = [3]
either: int | str = "s"
loc = Local()
for k in ["int", "str", "none", "ints", "mixed", "dict", "tuple", "point"]:
    x = v[k]
    print(k, type(x) is type(local_list), type(x) == type(local_dict), type(x) is type(local_tuple),
          type(x) is type(maybe), type(maybe_list) is type(x), type(x) is type(either), type(x) is type(loc),
          type(x) is type(3), type(x) != type("t"))
