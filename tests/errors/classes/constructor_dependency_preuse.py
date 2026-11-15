# error: is a class template
from mods.constructor_dependency import NestedChild, NestedErrors, Options

# No hierarchy has been requested when this standalone construction fails. Do not
# activate unrelated imported descendants simply to erase the annotation failure.
errors = NestedErrors(Options(True))
print(NestedChild(errors).read())
