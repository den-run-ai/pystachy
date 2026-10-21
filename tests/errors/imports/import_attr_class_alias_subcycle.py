# error: class 'emods.attrcyc.xa.C' cannot be used as a value
# (an alias through a package's submodule that imports the alias's module stays an error: in that
# circular import, CPython attaches xa to its package only once xa's code has run, so ya may find
# emods.attrcyc without it and raise AttributeError, as here)
import emods.attrcyc.xa

print("main")
