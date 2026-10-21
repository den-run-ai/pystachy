# An optional import of a module whose code raises ImportError, where only a function of that
# module (never called) imports the importing module back: its code runs to the raise, and the
# handler runs.
import loader.backuser

print(loader.backuser.NAME)
