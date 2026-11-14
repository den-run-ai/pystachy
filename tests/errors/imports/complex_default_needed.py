# error: expected complex, got int
# (a complex parameter's default that is a constant of another type is an error only where a
# call needs it, also in a program that tracks numeric identity)
# pystachy: dynamic-any
import mods.complexdefaults as m

print(m.plain(3j))
print(m.plain())
