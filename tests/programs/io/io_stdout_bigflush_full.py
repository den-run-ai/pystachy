# stdout is /dev/full: a flush of more text than stdout's buffer holds writes it directly, and
# when that fails CPython drops it, so nothing is left to fail at exit: status 1
import sys

sys.stdout.write("x" * 5000)
sys.stdout.flush()
print("not reached")
