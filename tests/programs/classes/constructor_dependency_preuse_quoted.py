from mods.constructor_dependency import Options
from mods.constructor_preuse import QuotedErrors


options = Options(True)
errors = QuotedErrors(options)
errors.items["quoted"].add("one")
print(errors.options is options, errors.options.strict, len(errors.items))
