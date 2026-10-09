# Documented deviation: dict.keys(), .values() and .items() return list snapshots, so they
# print as lists and compare equal to lists. CPython prints
# dict_keys([(1, 'a')]) dict_values([1]) dict_items([((1, 'a'), 1)]) False
d = {(1, "a"): 1}
print(d.keys(), d.values(), d.items(), d.keys() == [(1, "a")])
