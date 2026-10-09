# error: module attribute '__file__' is not supported
# CPython's modules have __file__, __doc__, __spec__ and the like; Pystachy's do not
import emods.empty

print(emods.empty.__file__)
