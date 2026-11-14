from mods.constructor_dependency import Child, Errors, Root


errors = Errors()
errors.items["x"].add("one")
child = Child(errors)
print(child.read(), child.errors is errors)
print(isinstance(child, Root), type(child).__name__)
errors.items["y"].add("two")
print(child.errors.count(), Child(errors).read())
