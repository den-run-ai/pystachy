from mods.constructor_dependency import NestedErrors, Options


# No subclass is used. Retrying this constructor must leave imported descendants lazy.
options = Options(True)
errors = NestedErrors(options)
print(errors.options is options, errors.options.strict, errors.count())
options.strict = False
errors.items["x"].add("one")
print(errors.options.strict, errors.options.flags["strict"], errors.count())
