# error: cannot import name 'T' from 'emods.tv_cyc_a' here: its code binds it only after the import that runs this one (not supported for a TypeVar)
# (CPython raises ImportError: cannot import name 'T' from partially initialized module 'emods.tv_cyc_a')
import emods.tv_cyc_a

print(emods.tv_cyc_a.ident(1))
