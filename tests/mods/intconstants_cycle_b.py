from . import intconstants_cycle_a

try:
    print(intconstants_cycle_a.early())
except NameError:
    print("cycle unbound")
