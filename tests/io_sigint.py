# Ctrl-C, as a SIGINT that a background shell sends once the program is computing, raises
# KeyboardInterrupt: buffered stdout is flushed, KeyboardInterrupt printed, and the program
# ends by SIGINT (status 130 in the shell)
import os

mark = "io_sigint_" + str(os.getpid()) + ".tmp"
r = os.system("(i=0; while [ ! -f " + mark + " ] && [ $i -lt 3000 ]; do sleep 0.01; i=$((i + 1)); done; kill -INT "
              + str(os.getpid()) + "; rm -f " + mark + ") &")
for i in range(5):
    print("line", i)
open(mark, "w").close()
total = 0
for i in range(100000000):
    total += len(str(i)) % 3
print("not reached", total)
