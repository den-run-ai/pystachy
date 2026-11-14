# error: has no attribute 'platform'
# platform has uname() and the Python version. platform.platform() describes the file of the
# Python executable too, and is not there.
import platform

print(platform.platform())
