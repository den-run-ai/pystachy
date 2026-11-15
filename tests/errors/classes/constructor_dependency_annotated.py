# error: unsupported type annotation
from mods.constructor_dependency import Errors
from mods.constructor_dependency_alias import Wrapped

errors = Errors()
errors.items["x"].add("one")
value = Wrapped(errors)
print(value.read(), value.errors is errors)
