# Failed imports discard the module's import bindings before the next attempt.
try:
    print(g.A)
except NameError:
    print("retry alias absent")
import good as g

raise ValueError("retry")
