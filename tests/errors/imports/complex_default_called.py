# error: mods.complexdefaults.scaled() is not supported: the default value of parameter 'factor' is a int, not the complex its annotation names
# (the def is left out, as it was before complex was a type: an error where the program calls it)
import mods.complexdefaults as m

print(m.scaled(2.0))
