# Imported constructors classify before method declarations; future and qualified annotations
# follow the same path as local annotations.
from mods.anyhold import Holder, ObjectHolder, ident

print(ident(1), ident("s"))
print(Holder(1).value, Holder("s").value)
print(ObjectHolder(2).value, ObjectHolder("object").value)
