# error: platform_flag_store.py:6: error: assigning 'eload.platflag._WIN' anything but the literal False is not supported: its module assigns it False once, so its tests of it are decided at compile time
# Through the module, another module may assign only the literal that a name holding a test of the
# platform holds (False here), as its module's tests of the name are decided at compile time
import eload.platflag

eload.platflag._WIN = True
