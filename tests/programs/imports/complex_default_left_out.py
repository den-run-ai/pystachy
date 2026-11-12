# An imported module's defs with complex parameters: one whose default is a value of another
# type is left out as it was before complex was a type (an error only if it were called), and
# its default is evaluated when the def runs, in order with the others
print("main: start")
import mods.complexdefaults as m

print(m.doubled(1j), m.shifted(1 + 1j), m.shifted(1j, 2j), m.plain(3j))
