# error: is a class template
from mods.constructor_dependency import Variable
from mods.constructor_preuse import VariableErrors


# A constructor argument still cannot establish one nominal layout for Variable.
errors = VariableErrors(Variable(3))
print(errors.options.item)
