# error: an except clause needs exception classes: a name, or a tuple of names
import os

kind = "OSError"
try:
    os.remove("/nonexistent")
except kind:
    pass
