"""Run a command and report wall time and peak RSS (ru_maxrss) of the child process."""

import json
import os
import subprocess
import sys
import time

start = time.perf_counter()
proc = subprocess.Popen(sys.argv[1:], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
_, status, usage = os.wait4(proc.pid, 0)
wall = time.perf_counter() - start
err = proc.stderr.read().decode().strip().splitlines()
print(json.dumps({"exit": os.waitstatus_to_exitcode(status), "wall_s": round(wall, 3),
                  "peak_rss_mib": round(usage.ru_maxrss / 1024, 1), "stderr_tail": err[-1:] }))
