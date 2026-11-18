from mods.constructor_dependency import NestedErrors as Problems, Options as Configuration


configuration = Configuration(False)
problems = Problems(configuration)
problems.items["alias"].add("one")
print(problems.options is configuration, problems.count(), problems.options.flags["strict"])
