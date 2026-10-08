# error: 'X' of module emods.circa is read here while that module is still being imported (a circular import), when only its constants (NAME = literal) can be read
import emods.circa

print(emods.circa.X)
