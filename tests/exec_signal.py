# os.execv: the process becomes another program, here a shell that kills itself by a signal, which
# ends the run as it ends the process (pystachy run too: no shell around it reports the signal).
# SIGTERM, not SIGSEGV: no core dump, so the shell's report does not depend on ulimit -c.
import os
import sys

for path, args in [("/nonexistent/sh", ["sh"]), ("/bin/sh", []), ("/bin/sh", [""])]:
    try:
        os.execv(path, args)
    except OSError as e:
        print("OSError", e)
    except ValueError as e:
        print("ValueError", e)
print("out", flush=True)
print("last", file=sys.stderr)
os.execv("/bin/sh", ["sh", "-c", "kill -TERM $$"])
