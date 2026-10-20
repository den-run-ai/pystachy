# error: assigning 'eload.tcflag.TYPE_CHECKING' anything but the literal False is not supported: its module assigns it False once
# Another module may assign a module's TYPE_CHECKING while that module's code still runs (here
# eload/tcback.py, which eload/tcflag.py imports between its TYPE_CHECKING = False and its test),
# so assigning it anything but False is an error where its module's tests of it are decided.
import eload.tcflag
