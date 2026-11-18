# error: 'ITEMS' of module reexpkg.listy is read here while that module is still being imported (a circular import), when only its constants (NAME = literal) can be read
# A copy of another module's list is no constant: reading it while its module is still being
# imported stays unsupported (CPython prints [1, 2]).
import reexpkg.listy
