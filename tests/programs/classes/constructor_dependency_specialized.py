from mods.constructor_dependency import Extracted, Variable

# The constructor code specializes for a template-valued input whose layout
# stays variable; the subclass stores only the converted integer.
print(Extracted(Variable(23)).read(), Extracted(Variable("29")).read())
