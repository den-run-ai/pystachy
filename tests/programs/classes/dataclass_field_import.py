from dataclasses import FrozenInstanceError, replace

import dataclass_field_mod
from dataclass_field_mod import Entry, Registry

r = Registry()
r.add(Entry("b", 2))
r.add(dataclass_field_mod.Entry("a", 2, ["x"], note="hidden"))
r.add(Entry("c", 1))
print(r.count, sorted(r.entries))
e = replace(r.entries[0], rank=9)
print(e, e > r.entries[0])
try:
    e.rank = 3
except FrozenInstanceError as err:
    print("frozen", err)
