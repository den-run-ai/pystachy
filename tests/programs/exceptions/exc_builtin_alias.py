# An imported module's name for a builtin exception class (from builtins import RuntimeError as
# error, as lib/_pystachy_thread.py binds _thread.error): except clauses, raise statements, calls
# and isinstance() see the builtin class, through the module and through a from-import
import mods.excalias
from mods.excalias import Missing, error

for k in range(2):
    try:
        mods.excalias.fail(k)
    except mods.excalias.error as e:
        print("error:", repr(e), isinstance(e, RuntimeError), isinstance(e, error))
    except Missing as e:
        print("Missing:", repr(e), isinstance(e, KeyError), isinstance(e, LookupError), isinstance(e, mods.excalias.Missing))
try:
    raise error("raised here")
except RuntimeError as e:
    print(repr(e))
m = Missing("m")
print(repr(m), str(m), isinstance(m, error))
