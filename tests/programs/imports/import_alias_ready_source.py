# The target's class statement ran, but the from-import did not bind its name.
try:
    from mods.alias_ready_failed_source import ReadyTarget
except ValueError as e:
    print("ValueError", e)
Alias = ReadyTarget
print(type(Alias()).__name__)
