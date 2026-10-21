import mods.alias_ready_cycle_a as source


def argument() -> int:
    print("cycle argument")
    return 4


try:
    print(source.Crate(argument()).v)
except AttributeError as e:
    print("AttributeError", "has no attribute 'Crate'" in str(e))
try:
    print(source.plus(argument()))
except AttributeError as e:
    print("AttributeError", "has no attribute 'plus'" in str(e))
try:
    print(source.also(argument()))
except AttributeError as e:
    print("AttributeError", "has no attribute 'also'" in str(e))
try:
    print(source.build())
except NameError as e:
    print("NameError", e)
try:
    print(source.through_import())
except AttributeError as e:
    print("AttributeError", "has no attribute 'plus'" in str(e))
try:
    print(source.invoke())
except NameError as e:
    print("NameError", e)
