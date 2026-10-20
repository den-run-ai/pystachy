# atexit's callbacks where an exception that nothing catches ends the program: its message first,
# then the callbacks; the status stays 1
import atexit

atexit.register(print, "bye")
raise KeyError("k")
