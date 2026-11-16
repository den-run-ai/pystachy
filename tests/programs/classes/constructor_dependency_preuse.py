from mods.constructor_dependency import NestedChild, NestedErrors, Options

# The standalone dependency is constructed before any hierarchy is requested.
errors = NestedErrors(Options(True))
print(NestedChild(errors).read())
