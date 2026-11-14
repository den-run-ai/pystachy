# error: module attribute '__spec__' is not supported
# CPython's modules have __spec__, __loader__ and the like; Pystachy's have __name__, __doc__ and __file__
import emods.empty

print(emods.empty.__spec__)
