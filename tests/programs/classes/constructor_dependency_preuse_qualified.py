import mods.constructor_dependency as models
import mods.constructor_preuse as wrappers


options = models.Options(True)
errors = wrappers.QualifiedErrors(options)
errors.items["qualified"].add("one")
print(errors.options is options, errors.options.flags["strict"], len(errors.items))
