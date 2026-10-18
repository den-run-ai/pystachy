# a Python exception whose str() raises: what str() raised comes instead (as the twin's str(e) raises
# it), and if that one's str() raises too, its class with "<exception str() failed>"
from pyobj import import_module

m = import_module("side_badstr")
for f in ["boom", "boom2"]:
    try:
        m.attr(f).call([])
    except Exception as e:
        print(f, "caught", e)
