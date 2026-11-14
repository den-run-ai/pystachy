# error: module 'sysconfig' has no attribute 'get_platform'
# sysconfig answers for the Pystachy home and the Python version. get_platform() names the
# machine, which CPython reads with os.uname(): it is not there.
import sysconfig

print(sysconfig.get_platform())
