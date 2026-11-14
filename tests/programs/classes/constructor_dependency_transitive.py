from mods.constructor_dependency import NestedChild, NestedErrors, Options

# Resolve the demanded hierarchy before constructing its template-valued dependencies.
value = NestedChild(NestedErrors(Options(True)))
print(value.read(), value.errors.options.flags["strict"])
value.errors.items["x"].add("one")
print(value.errors.count(), NestedChild(value.errors).read())
