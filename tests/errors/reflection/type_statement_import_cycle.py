# error: cannot import name 'Grid' from 'emods.ts_cyc_a' here: its code binds it only after the import that runs this one (not supported for a type alias)
# (CPython raises ImportError: cannot import name 'Grid' from partially initialized module 'emods.ts_cyc_a')
import emods.ts_cyc_a

print(emods.ts_cyc_a.height([[1]]))
