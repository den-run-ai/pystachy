# error: an except clause needs builtin exception classes: a name, or a tuple of names
import os

try:
    os.remove("/nonexistent")
except os.error:
    pass
