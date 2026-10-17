# A module of the program declares a C function of libpython that lib/pyobj.py calls too, and is
# imported first (side_sym.py): its function is looked up when its def runs, pyobj's is called
# directly, and the program's IR declares the C function once
from side_sym import Py_IsInitialized
from pyobj import of_int

print(Py_IsInitialized(), of_int(5).to_int())
