# error: unsupported type annotation
# CPython evaluates a nested def's annotations where its function runs, and the name that only an
# if TYPE_CHECKING: import binds is unbound there (NameError): it must be quoted
import tcbad.model
import tcbad.nested

print(tcbad.nested.run(tcbad.model.Model()))
