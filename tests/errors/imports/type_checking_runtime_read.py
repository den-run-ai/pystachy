# error: name 'Model' is not defined
# A name that only an if TYPE_CHECKING: import binds is unbound when code reads it, as CPython
# never runs that import: it types annotations only
import tcbad.model
import tcbad.runtime_read

print(tcbad.runtime_read.make())
