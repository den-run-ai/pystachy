from mods.constructor_dependency import Errors
from mods.constructor_dependency_alias import Quoted

errors = Errors()
errors.items["x"].add("one")
value = Quoted(errors)
print(value.read(), value.errors is errors)
