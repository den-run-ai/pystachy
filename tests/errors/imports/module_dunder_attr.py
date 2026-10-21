# error: module attribute '__file__' is not supported
# CPython's modules have __file__, __spec__ and the like; Pystachy's have only __name__ and __doc__
import emods.empty

print(emods.empty.__file__)
