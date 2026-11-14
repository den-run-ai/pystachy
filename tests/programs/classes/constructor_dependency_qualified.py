from mods.constructor_dependency import Errors
from mods.constructor_dependency_alias import Qualified

errors = Errors()
errors.items["x"].add("one")
value = Qualified(errors)
print(value.read(), value.errors is errors)
