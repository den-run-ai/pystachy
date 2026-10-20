# error: module 'eload.cyc_call' may import this module as its code runs (through a call), before that raises ImportError
# The failing module's code calls a function of its own that imports the importing module back.
import eload.cyc_user
