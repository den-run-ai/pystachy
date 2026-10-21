# error: del of 'eload.tcdel.TYPE_CHECKING' is not supported: its module assigns it False once
# A module that imports itself may delete its TYPE_CHECKING through the module (eload/tcdel.py),
# and its test that follows then raises NameError in CPython, so that is an error.
import eload.tcdel
