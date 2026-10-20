# error: cannot import name 'Row' from 'emods.ta_cyc_a' here: its code binds it only after the import that runs this one (not supported for a type alias)
# (CPython raises ImportError: cannot import name 'Row' from partially initialized module 'emods.ta_cyc_a')
import emods.ta_cyc_a

print(emods.ta_cyc_a.width([1, 2]))
