# stdout is /dev/full: more pending text than stdout's buffer holds is written directly when
# the program's code ends; CPython drops it when that fails, so the flush at exit has nothing
# to write and the status is 0
import sys

sys.stdout.write("x" * 5000)
sys.stderr.write("end\n")
