# error: emods/checking.py:7: error: name 'Iterable' is not defined
# An imported module's annotation that names what only an "if TYPE_CHECKING:" block imports is a
# NameError where the def runs, at the import, used or not: not an error deferred to a use.
import emods.checking
print(emods.checking.count())
