# error: an except clause needs exception classes: a name, or a tuple of names
import os

try:
    os.remove("/nonexistent")
except os.error:
    pass
