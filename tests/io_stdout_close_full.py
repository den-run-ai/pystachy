# stdout is /dev/full: sys.stdout.close() flushes, and that failure raises; the closed stdout
# is not flushed again at exit, so the status is 1
import sys

print("x")
sys.stdout.close()
sys.stderr.write("not reached\n")
