# error: module 'sysconfig' has no attribute 'get_makefile_filename'
# Pystachy is not built with CPython's Makefile and pyconfig.h: the functions that find or
# read them (get_makefile_filename(), get_config_h_filename(), parse_config_h()) are not there.
import sysconfig

print(sysconfig.get_makefile_filename())
