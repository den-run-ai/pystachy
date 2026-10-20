# stdout is /dev/full: CPython flushes stdout when the program's code ends (ignoring a failure,
# but keeping text its buffer held) and again at exit, where the failure is reported: status 120
import sys

print("x")
sys.stderr.write("end\n")
