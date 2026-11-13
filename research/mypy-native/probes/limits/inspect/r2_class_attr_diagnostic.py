# In an imported module, the diagnostic for a class attribute whose type is not inferred names
# the failing attribute ('marker', r2mod.py line 18) but reports the line and the expression of
# the class's first attribute statement (line 16, 'Kind.A').
import r2mod

print(r2mod.Holder.FIRST, r2mod.Holder.marker is r2mod._marker)
