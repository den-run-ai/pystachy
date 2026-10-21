# error: assigning 'eload.tcself.TYPE_CHECKING' anything but the literal False is not supported: its module assigns it False once
# A module's own code may assign its TYPE_CHECKING through the module once it imports itself
# (eload/tcself.py), and its test that follows then sees the new value in CPython, so that is an
# error too.
import eload.tcself
