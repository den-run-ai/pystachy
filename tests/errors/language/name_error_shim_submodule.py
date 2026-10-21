# error: name 'sub' is not defined
# A package's try that reads the name of a submodule is not decided at compile time: an import of
# the submodule binds that name in the package (tests/shimpkg/)
import shimpkg

print(shimpkg.VALUE)
