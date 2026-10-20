# Ctrl-C interrupts a select wait using the existing runtime signal behavior.
import os
import select

mark = "select_sigint_" + str(os.getpid()) + ".tmp"
os.system("(i=0; while [ ! -f " + mark + " ] && [ $i -lt 3000 ]; do sleep 0.01; i=$((i + 1)); done; kill -INT "
          + str(os.getpid()) + "; rm -f " + mark + ") &")
print("waiting")
open(mark, "w").close()
select.select([], [], [], 5)
print("not reached")
