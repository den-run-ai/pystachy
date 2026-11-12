# error: name 'Model' is not defined
# Without postponed evaluation CPython evaluates the annotation where the def runs, and the
# TYPE_CHECKING-only name is unbound there (NameError)
import tcbad.model
import tcbad.eager

print(tcbad.eager.describe)
