from mods.constructor_dependency import Errors
from mods.constructor_dependency_alias import Aliased

errors = Errors()
errors.items["x"].add("one")
value = Aliased(errors)
print(value.read(), value.errors is errors)
